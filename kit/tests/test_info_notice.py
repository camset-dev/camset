"""--info-ok "ROW=PHRASE" (kit/crawl_run.py, kit/prove_run.py): a row whose Right opens an information notice before its
screen (the a1 II's Different Set for Still/Mv: "You can set different settings for still image mode and movie mode in
the next screen. ...", a single OK, then a checklist of seven boxes) is walked and proved only where the run names the
row and the notice's opening words, matched word for word; the OK goes out once a visit, and only on a notice that
explains and asks nothing. Without the flag nothing changes: the crawl records "notice" after Right and MENU, and the
checklist prover fails at the notice. Fake cameras, OCR and readers only: nothing here talks to a camera, a reader or a
network.
"""
import io
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from camkit import crawl, ocr  # noqa: E402
from camkit.runs import Run  # noqa: E402

ROW = "Different Set for Still/Mv"
# the a1 II's notice as written, its tick-box glyph and sentence ends with it (runner.notice_words leaves both out)
WORDS = ("You can set different settings for still image mode and movie mode in the next screen. "
         "The setting set for ☑ is independent.")
INFO = f"{ROW}={WORDS}"
BOXES = ["Aperture", "Shutter Speed", "ISO", "Exposure Comp.", "Metering Mode", "White Balance", "Picture Profile"]
OK_BAR = (200, 340, 240, 55)                  # the notice's orange OK bar (proving.screens.notice_focus)
# the row labels the kit knows in these tests (the definition's menu or the page model's, runner.info_ok_or_exit)
KNOWN = {ROW, "DISP (Screen Disp) Set", "ISO", "Top", "Av Auto/Manual Switch", "Format", "Something", "Initialize",
         "Bluetooth Function", "Language", "Access Authen. Info", "Audio Signals", "Network", "Wi-Fi Direct Info.",
         "DeleteAll", "SettingReset", "ScreenReader", "AudioSignals", "Steady.Shot", "WPS Push"}
PHRASE = ("you can set different settings for still image mode and movie mode in the next screen the setting set for "
          "is independent")


def line(text, y, x=40, w=560):
    return ocr.Line(text=text, conf=0.9, x=x, y=y, w=w, h=30)


SENTENCE = [line("You can set different settings for still image mode and", 100),
            line("movie mode in the next screen. The setting set for", 140), line("is independent.", 180)]
OK_LINE = line("OK", 352, x=300, w=40)        # inside OK_BAR
NOTICE = SENTENCE + [OK_LINE]


class NoticeCamera:
    """A menu row whose Right opens an information notice, OK on it a checklist (seven boxes and an OK button: Down
    wraps after 8 places), Enter on a box flipping its tick and on the OK button applying and going back to the row,
    MENU back to the row from anywhere: the a1 II's Different Set for Still/Mv (the plan's section 1). after_ok: the
    screen the notice's OK opens. Every key is kept; each place has a frame of its own name."""
    def __init__(self, tmp_path=Path("."), after_ok="checklist"):
        self.where, self.cursor, self.keys, self.presses, self.after_ok = "row", 0, [], 0, after_ok
        self.ticks, self.tmp = [False] * len(BOXES), Path(tmp_path)

    @property
    def frame(self):
        return SimpleNamespace(path=self.tmp / f"{self.where}.png", image=None)

    def press(self, key, **kw):
        self.presses += 1
        self.keys.append(key)
        if key == "menu":
            self.where, self.cursor = "row", 0
        elif self.where == "row" and key == "right":
            self.where = "notice"
        elif self.where == "notice" and key == "enter":
            self.where, self.cursor = self.after_ok, 0
        elif self.where == "checklist" and key == "down":
            self.cursor = (self.cursor + 1) % (len(BOXES) + 1)
        elif self.where == "checklist" and key == "enter":
            if self.cursor < len(BOXES):
                self.ticks[self.cursor] = not self.ticks[self.cursor]
            else:
                self.where, self.cursor = "row", 0                  # OK: applied, back on the row

    def read(self):
        sig = f"check{self.cursor}" if self.where == "checklist" else self.where
        kind = {"row": "menu"}.get(self.where, self.where)
        return SimpleNamespace(kind=kind, signature=sig, struct=sig, bits=None, row=0, at_end=None,
                               at_start=(self.cursor == 0) if self.where == "checklist" else None, scroll=None,
                               glyphs={}, focus="button" if self.cursor == len(BOXES) else "rows")


def fake_ocr(monkeypatch, notice_lines, lit=OK_BAR):
    """OCR reads `notice_lines` on the notice's frame and nothing elsewhere; the notice's lit bar is at `lit`."""
    from proving import screens
    monkeypatch.setattr(ocr, "read", lambda paths, eng=None: {p: (notice_lines if Path(p).name == "notice.png" else [])
                                                              for p in paths})
    monkeypatch.setattr(screens, "notice_focus", lambda image: lit)


def parsed(*values, rows=None):
    import runner
    return runner.info_ok_or_exit(list(values), rows, labels=KNOWN)


def info_ok(lit_bar=ROW, values=(INFO,)):
    """kit/crawl_run.py's callback for `values`, the lit bar before Right read as `lit_bar`."""
    import crawl_run
    return crawl_run.info_ok_pass(parsed(*values)), lit_bar


def visit(cam, cb=None, label=ROW, row=None, network=frozenset()):
    return crawl.visit_row(cam, cam.read(), {"page": "Setup > Operation Customize"}, 0, row or {"label": label},
                           network=network, info_ok=cb)


def judged(monkeypatch, lines, lit_bar=ROW, name=ROW, lit=OK_BAR):
    """proving.screens.pass_named_notice on a NoticeCamera at its notice (Right pressed), OCR reading `lines`: (its
    answer, the keys pressed after Right)."""
    from proving import screens
    fake_ocr(monkeypatch, lines, lit)
    cam = NoticeCamera()
    cam.press("right")
    got = screens.pass_named_notice(cam, name, PHRASE, lit_bar)
    return got, cam.keys[1:]


# ---------------------------------------------------------------------------------------------- the crawl (camkit.crawl)

def test_without_the_flag_the_crawl_records_the_notice_after_two_presses():
    cam = NoticeCamera()
    r = visit(cam)
    assert cam.keys == ["right", "menu"] and r.outcome == "notice" and r.presses == 2 and r.info_ok is None
    cam = NoticeCamera()                     # the whole lap too: one position, the same two presses
    out = crawl.crawl(cam, [{"page": "p", "row": 0, "signature": "row", "kind": "menu"}],
                      {"p": {"breadcrumb": "Setup > Operation Customize", "page": "50/63", "rows": [{"label": ROW}]}})
    assert out.rows[0].outcome == "notice" and out.presses == 2 and cam.keys == ["right", "menu"]


def test_a_callback_that_takes_the_notice_gets_one_enter_and_the_checklist_walked():
    def took(cam, name, before):
        assert name == ROW and before.path.name == "row.png"       # the frame read before Right
        cam.press("enter")
        return {"row": name, "frame": "notice.png"}
    cam = NoticeCamera()
    r = visit(cam, took)
    assert cam.keys[:2] == ["right", "enter"] and cam.keys[-1] == "menu" and cam.keys.count("enter") == 1
    assert cam.keys.count("down") == len(BOXES) + 1 and r.outcome == "walked" and r.kind == "checklist"
    assert r.info_ok == {"row": ROW, "frame": "notice.png"} and len(r.walk.options) == len(BOXES) + 1


def test_a_callback_that_refuses_or_names_nothing_presses_nothing():
    cam = NoticeCamera()
    r = visit(cam, lambda cam, name, before: {"refused": "not the notice named (notice.png)"})
    assert cam.keys == ["right", "menu"] and r.outcome == "notice (named, not passed: not the notice named (notice.png))"
    cam = NoticeCamera()
    r = visit(cam, lambda cam, name, before: None)              # a row the run does not name: as before
    assert cam.keys == ["right", "menu"] and r.outcome == "notice"


def test_after_the_ok_a_screen_the_walkers_do_not_know_is_left_with_menu():
    def took(cam, name, before):
        cam.press("enter")
        return {"row": name, "frame": "notice.png"}
    for after in ("notice", "submenu", "unknown"):
        cam = NoticeCamera(after_ok=after)
        r = visit(cam, took)
        assert cam.keys == ["right", "enter", "menu"], (after, cam.keys)
        assert r.outcome == f"notice passed: a {after} screen after its OK, left unwalked"


def test_the_callback_is_never_called_on_a_row_a_network_decision_opened():
    from camkit import safety
    called = []
    cam = NoticeCamera()
    row = {"label": "Bluetooth Function", "never_open": safety.never_open("Bluetooth Function")}
    r = crawl.visit_row(cam, cam.read(), {"page": "Network > Bluetooth"}, 0, row,
                        network={"Bluetooth Function": "2026-11-13"}, info_ok=lambda *a: called.append(a))
    assert called == [] and cam.keys == ["right", "menu"] and r.outcome.startswith("network row: a notice screen")


class SubmenuCamera(NoticeCamera):
    """A top row whose Right opens a submenu of two rows ("Plain", which Right leaves as it is, and the notice row), Down
    wrapping between them, Left back to the top row; MENU inside the notice row's screens back to that submenu row."""
    def press(self, key, **kw):
        if self.where in ("row", "sub0", "sub1"):
            self.presses += 1
            self.keys.append(key)
            self.where = {("row", "right"): "sub0", ("sub0", "down"): "sub1", ("sub1", "down"): "sub0",
                          ("sub1", "right"): "notice", ("sub0", "left"): "row", ("sub1", "left"): "row"}.get(
                (self.where, key), self.where)
            return
        super().press(key)
        if key == "menu":
            self.where = "sub1"

    def read(self):
        if self.where.startswith("sub"):
            return SimpleNamespace(kind="submenu", signature=self.where, struct=self.where, bits=None,
                                   row=int(self.where[-1]), at_end=None, at_start=None, scroll=None, glyphs={},
                                   focus="rows")
        return super().read()


def test_the_crawl_hands_the_callback_into_a_submenu_with_the_rows_whole_name():
    names = []

    def took(cam, name, before):
        names.append(name)
        cam.press("enter")
        return {"row": name, "frame": "notice.png"}
    cam = SubmenuCamera()
    r = crawl.visit_row(cam, cam.read(), {"page": "Setup > X"}, 0, {"label": "Top"},
                        labels=lambda c: ("sub", [{"label": "Plain"}, {"label": ROW}]), info_ok=took)
    assert names == [f"Top > {ROW}"] and cam.keys.count("enter") == 1 and r.outcome == "submenu crawled"
    sub = r.walk.rows[1]
    assert sub.outcome == "walked" and sub.info_ok == {"row": f"Top > {ROW}", "frame": "notice.png"}


# ---------------------------------------------------------------------------------------------- crawl_run's judgement

def crawl_with(monkeypatch, notice_lines, lit_bar=ROW, label=ROW, lit=OK_BAR):
    import crawl_run
    fake_ocr(monkeypatch, notice_lines, lit)
    cb, bar = info_ok(lit_bar)
    monkeypatch.setattr(crawl_run, "lit_text", lambda image, path: bar if Path(path).name == "row.png" else "")
    cam = NoticeCamera()
    return cam, visit(cam, cb, label=label)


def test_the_named_notice_is_passed_and_its_checklist_walked(monkeypatch, capsys):
    cam, r = crawl_with(monkeypatch, NOTICE)
    assert cam.keys[:2] == ["right", "enter"] and cam.keys.count("enter") == 1 and r.outcome == "walked"
    assert r.info_ok == {"row": ROW, "frame": "notice.png"} and r.kind == "checklist"
    import crawl_run
    row = crawl_run.summary(r)
    assert row["info_ok"] == {"row": ROW, "frame": "notice.png"} and row["kind"] == "checklist"
    said = [x for x in capsys.readouterr().out.splitlines() if not x.startswith("--info-ok:")]    # the run's own phrase
    assert not [x for x in said if "independent" in x]               # no text read off the notice is printed


@pytest.mark.parametrize("why,lines,lit_bar,lit,refused", [
    ("the lit bar before Right is another row", NOTICE, "DISP (Screen Disp) Set", OK_BAR, "not the row named"),
    ("the lit bar before Right reads nothing", NOTICE, "", OK_BAR, "not the row named"),
    ("another notice", [line("This function is currently disabled.", 100), OK_LINE], ROW, OK_BAR,
     "not the notice named"),
    ("a confirmation-like notice", [line("Delete all?", 100), OK_LINE, line("Cancel", 352, x=420, w=60)], ROW, OK_BAR,
     "not the notice named"),
    ("the named words with a confirmation's", SENTENCE + [line("All data will be lost.", 220), OK_LINE], ROW, OK_BAR,
     "reads as a confirmation"),
    ("two buttons", NOTICE + [line("Cancel", 352, x=460, w=60)], ROW, OK_BAR, "not a single OK"),
    ("Cancel alone, lit", SENTENCE + [line("Cancel", 352, x=300, w=60)], ROW, OK_BAR, "not a single OK"),
    ("the lit item is no OK (a Don't show this again box)",
     SENTENCE + [line("Don't show this again.", 260, x=210, w=220), OK_LINE], ROW, (200, 250, 240, 50),
     "the lit button is not OK"),
    ("nothing lit", NOTICE, ROW, None, "the lit button is not OK"),
    ("an identity notice", SENTENCE + [line("Enter the account of the server.", 220), OK_LINE], ROW, OK_BAR,
     "identity or credentials"),
    ("a never-open name on the notice", SENTENCE + [line("Screen Reader", 220), OK_LINE], ROW, OK_BAR,
     "never-open list"),
])
def test_a_notice_failing_any_guard_gets_no_enter(monkeypatch, why, lines, lit_bar, lit, refused):
    cam, r = crawl_with(monkeypatch, lines, lit_bar=lit_bar, lit=lit)
    assert cam.keys == ["right", "menu"], (why, cam.keys)
    assert r.outcome.startswith("notice (named, not passed: ") and r.info_ok is None, (why, r.outcome)
    assert refused in r.outcome, (why, r.outcome)
    for t in ("independent", "Delete all", "account", "Screen Reader"):    # no text read off the screen is kept
        assert t not in r.outcome, (why, r.outcome)


def test_a_row_the_run_does_not_name_is_left_as_ever(monkeypatch):
    cam, r = crawl_with(monkeypatch, NOTICE, lit_bar="DISP (Screen Disp) Set", label="DISP (Screen Disp) Set")
    assert cam.keys == ["right", "menu"] and r.outcome == "notice"


# ---------------------------------------------------------------------------------------------- the notice's judgement

@pytest.mark.parametrize("lines,refused", [
    # a question, anywhere
    (SENTENCE + [line("Apply now?", 220), OK_LINE], "it asks a question"),
    (SENTENCE + [line("Deleteall?", 220), OK_LINE], "it asks a question"),
    (SENTENCE + [line("Proceed?", 220), OK_LINE], "it asks a question"),
    (SENTENCE + [line("Register?", 220), OK_LINE], "it asks a question"),
    (SENTENCE + [line("Ready？", 220), OK_LINE], "it asks a question"),        # a full-width question mark
    # a confirmation's words, run together or inflected
    (SENTENCE + [line("Deleteall", 220), OK_LINE], "its words run together"),
    (SENTENCE + [line("The images will be deleted.", 220), OK_LINE], "names a button, a choice or an action"),
    (SENTENCE + [line("All settings are overwritten.", 220), OK_LINE], "names a button, a choice or an action"),
    (SENTENCE + [line("Executed.", 220), OK_LINE], "names a button, a choice or an action"),
    (SENTENCE + [line("Willbelost", 220), OK_LINE], "its words run together"),
    # a second button, read whole or not, or a word of a choice or an action beside the OK
    (SENTENCE + [line("OK Cancel", 352, x=280, w=120)], "not a single OK: 0 button lines"),
    (NOTICE + [line("Cance1", 352, x=460, w=60)], "names a button, a choice or an action"),
    (NOTICE + [line("x Cancel", 352, x=440, w=80)], "names a button, a choice or an action"),
    (NOTICE + [line("Cancel/", 352, x=460, w=60)], "names a button, a choice or an action"),
    (NOTICE + [line("Back", 352, x=460, w=60)], "names a button, a choice or an action"),
    (SENTENCE + [line("Register", 220), OK_LINE], "names a button, a choice or an action"),
    (SENTENCE + [line("Apply these settings", 220), OK_LINE], "names a button, a choice or an action"),
    (SENTENCE + [line("Start recording when OK is pressed.", 220), OK_LINE], "names a button, a choice or an action"),
    # anything on or below the OK's line
    (NOTICE + [line("Display", 420, x=200, w=100)], "on or below its OK's band"),
    (NOTICE + [line("Display", 352, x=60, w=100)], "on or below its OK's band"),
    # no OK line at all
    (SENTENCE, "not a single OK: 0 button lines"),
])
def test_a_notice_that_asks_or_acts_gets_no_enter(monkeypatch, lines, refused):
    got, keys = judged(monkeypatch, lines)
    assert keys == [] and "refused" in got and refused in got["refused"], (got, keys)


def test_the_judgement_presses_only_on_a_notice(monkeypatch):
    from proving import screens
    fake_ocr(monkeypatch, NOTICE)
    cam = NoticeCamera()                                             # still on the row: no notice up
    got = screens.pass_named_notice(cam, ROW, PHRASE, ROW)
    assert got == {"refused": "not a notice (menu, row.png)"} and cam.keys == []


@pytest.mark.parametrize("name,lit_bar,passes", [
    (ROW, f"{ROW}  On", True),                     # the bar starts with the row, a value after it: bar_on_row alone
    (ROW, f"S{ROW}", True),                        # an icon glued on in front: page_model.same_text alone
    ("Av Auto/Manual Switch", "Tv Auto/Manual Switch", False),       # same_text, but its short first word is another
])
def test_the_lit_bar_before_right_is_read_as_the_row_each_way(monkeypatch, name, lit_bar, passes):
    got, keys = judged(monkeypatch, NOTICE, lit_bar=lit_bar, name=name)
    if passes:
        assert got == {"row": name, "frame": "notice.png"} and keys == ["enter"]
    else:
        assert got == {"refused": "the lit bar read before Right is not the row named"} and keys == []


def test_the_phrase_is_found_in_the_folded_reading(monkeypatch):
    cyrillic = [line("Yоu can set different settings for still image mode and", 100), *SENTENCE[1:], OK_LINE]
    got, keys = judged(monkeypatch, cyrillic)
    assert got == {"row": ROW, "frame": "notice.png"} and keys == ["enter"]


def test_punctuation_glyphs_and_spacing_are_ignored_in_the_notice(monkeypatch):
    marked = [line("You  can set different settings – for still image mode and", 100),
              line("movie mode in the next screen; the setting set for ☑", 140), line("is independent!", 180),
              OK_LINE]
    got, keys = judged(monkeypatch, marked)
    assert got == {"row": ROW, "frame": "notice.png"} and keys == ["enter"]


@pytest.mark.parametrize("why,lines", [
    ("the glyph read as a letter", [*SENTENCE[:2], line("M is independent.", 180), OK_LINE]),
    ("the glyph read as two letters", [*SENTENCE[:2], line("MI is independent.", 180), OK_LINE]),
    ("the glyph glued to a word", [SENTENCE[0], line("movie mode in the next screen. The setting set forM", 140),
                                   SENTENCE[2], OK_LINE]),
    ("the glyph read as a line of its own, inside the text", [*SENTENCE[:2], line("Ø", 180, x=40, w=20),
                                                             line("is independent.", 180, x=70), OK_LINE]),
    ("a letter read for another", [line("You can set different settinqs for still image mode and", 100),
                                   *SENTENCE[1:], OK_LINE]),
])
def test_the_whole_text_phrase_takes_an_icon_read_as_a_letter_or_two(monkeypatch, why, lines):
    got, keys = judged(monkeypatch, lines)
    assert got == {"row": ROW, "frame": "notice.png"} and keys == ["enter"], (why, got)


@pytest.mark.parametrize("why,lines,said", [
    ("an extra sentence", NOTICE + [line("Settings return to defaults.", 220)], "letters or digits beyond the phrase"),
    ("an extra sentence", NOTICE + [line("Images are sent.", 220)], "a word it does not name"),
    ("an extra sentence", NOTICE + [line("This will clear your saved faces.", 220)], "a word it does not name"),
    ("an extra sentence", NOTICE + [line("Power will be turned off.", 220)], "a word it does not name"),
    ("an extra sentence on the text's own line", [*SENTENCE[:2], line("is independent. Images are sent.", 180),
                                                  OK_LINE], "a word it does not name"),
    ("a button stacked above the OK", NOTICE + [line("Stop", 300, x=300, w=50)], "a word it does not name"),
    ("a button stacked above the OK", NOTICE + [line("Skip", 300, x=300, w=50)], "a word it does not name"),
    ("a button stacked above the OK", NOTICE + [line("Later", 300, x=300, w=50)], "a word it does not name"),
    ("a stray letter stacked above the OK", NOTICE + [line("x", 300, x=310, w=15)], "a line outside its text"),
    ("a stray mark stacked above the OK", NOTICE + [line("•", 300, x=310, w=15)], "a line outside its text"),
    ("the glyph read as three letters", [*SENTENCE[:2], line("MIR is independent.", 180), OK_LINE],
     "a word it does not name"),
])
def test_a_notice_the_phrase_does_not_wholly_name_gets_no_enter(monkeypatch, capsys, why, lines, said):
    got, keys = judged(monkeypatch, lines)
    assert keys == [] and "refused" in got and said in got["refused"], (why, got)
    assert "give its whole text as written" in got["refused"] and "the notice reads" in capsys.readouterr().out


@pytest.mark.parametrize("why,lines,passes", [
    ("the box's line alone", NOTICE + [line("Don't show this again.", 260, x=210, w=220)], True),
    ("the box's line, its apostrophe dropped", NOTICE + [line("Dont show this again", 260, x=210, w=220)], True),
    ("the box's line with more words on it", NOTICE + [line("Don't show this again. Settings revert", 260, x=40)],
     False),
])
def test_a_dont_show_line_is_set_aside_only_when_it_says_nothing_else(monkeypatch, why, lines, passes):
    got, keys = judged(monkeypatch, lines)
    if passes:
        assert got == {"row": ROW, "frame": "notice.png"} and keys == ["enter"], (why, got)
    else:
        assert keys == [] and "a word it does not name" in got.get("refused", ""), (why, got)


def test_a_phrase_that_names_the_boxs_words_too_is_taken(monkeypatch):
    from proving import screens
    fake_ocr(monkeypatch, NOTICE + [line("Don't show this again.", 260, x=210, w=220)])
    cam = NoticeCamera()
    cam.press("right")
    assert screens.pass_named_notice(cam, ROW, f"{PHRASE} don't show this again", ROW) == {"row": ROW,
                                                                                            "frame": "notice.png"}


@pytest.mark.parametrize("why,lines,passes", [
    ("isn't", [*SENTENCE[:2], line("isn't independent.", 180), OK_LINE], False),
    ("can't", [line("You can't set different settings for still image mode and", 100), *SENTENCE[1:], OK_LINE], False),
    ("unset, mid-line", [line("You can unset different settings for still image mode and", 100), *SENTENCE[1:], OK_LINE],
     False),
    ("a letter glued on mid-line", [line("You can xset different settings for still image mode and", 100), *SENTENCE[1:],
                                    OK_LINE], False),
    ("unset, a line's first word", [line("You can", 100, w=80), line("unset different settings for still image mode and",
                                                                       100, x=130, w=480), *SENTENCE[1:], OK_LINE], False),
    ("isnt, its apostrophe dropped, a line's first word", [*SENTENCE[:2], line("isnt independent.", 180), OK_LINE],
     False),
    ("an icon letter glued to a line's first word", [*SENTENCE[:2], line("Mis independent.", 180), OK_LINE], True),
    ("an icon letter glued to a line's last word", [*SENTENCE[:2], line("is independentM", 180), OK_LINE], True),
])
def test_a_negation_is_one_word_and_glued_letters_sit_only_at_a_lines_ends(monkeypatch, why, lines, passes):
    got, keys = judged(monkeypatch, lines)
    if passes:
        assert got == {"row": ROW, "frame": "notice.png"} and keys == ["enter"], (why, got)
    else:
        assert keys == [] and "refused" in got, (why, got)


def test_how_far_a_notices_word_may_differ_from_the_phrases():
    from proving import screens
    from runner import joined, notice_words
    assert notice_words("☑ isn’t independent. You can't") == "isn't independent you can't"
    wc = screens.word_cover
    assert wc("in", "is") is None and wc("mode", "mobe") == 3            # a slip in words of four letters or more only
    assert wc("settings", "settinqs") == 7 and wc("settings", "setings") == 7 and wc("setting", "settings") == 7
    assert wc("set", "xxset", edge=True) == 3 and wc("set", "setxx", edge=True) == 3       # two glued letters at most
    assert wc("set", "xxxset", edge=True) is None and wc("set", "unreset", edge=True) is None
    assert wc("set", "xset") is None                                     # never mid-line
    assert wc("a", "ab", edge=True) is None and wc("is", "Mis".lower(), edge=True) == 2     # a word of two letters or more
    assert wc("set", "s'set", edge=True) is None                         # glued letters or digits only
    assert joined("prefixed", ["fix"]) is None and joined("prefixedall", ["fixe"]) == "fixe"  # names of four letters up


def test_one_slip_costs_its_letter_against_the_limit(monkeypatch):
    """Ten short marks the phrase skips plus one letter read for another: eleven letters unaccounted for, refused."""
    slipped = [line("You can set different settinqs for still image mode and", 100), SENTENCE[1],
               line("is independent. xq zv wk jp qz", 180), OK_LINE]
    got, keys = judged(monkeypatch, slipped)
    assert got.get("refused", "").startswith("the notice has 11 letters or digits beyond the phrase: ") and keys == []


def test_at_most_ten_letters_of_the_notice_may_go_unaccounted_for(monkeypatch):
    """Short marks the phrase skips (each a letter or two, inside the text's lines) are let through up to INFO_OK_SLACK
    letters and digits in all, never more."""
    import runner
    assert runner.INFO_OK_SLACK == 10
    ten = [*SENTENCE[:2], line("is independent. xq zv wk jp qz", 180), OK_LINE]
    got, keys = judged(monkeypatch, ten)
    assert got == {"row": ROW, "frame": "notice.png"} and keys == ["enter"]
    twelve = [*SENTENCE[:2], line("is independent. xq zv wk jp qz vx", 180), OK_LINE]
    got, keys = judged(monkeypatch, twelve)
    assert got.get("refused", "").startswith("the notice has 12 letters or digits beyond the phrase: ") and keys == []


def test_a_short_phrase_on_a_long_notice_is_refused_and_says_how_much_is_left(monkeypatch, capsys):
    from proving import screens
    fake_ocr(monkeypatch, NOTICE)
    cam = NoticeCamera()
    cam.press("right")
    got = screens.pass_named_notice(cam, ROW, "different settings for", ROW)
    left = sum(map(len, PHRASE.split())) - len("differentsettingsfor")
    assert got == {"refused": f"the notice has {left} letters or digits beyond the phrase, a word it does not name: "
                              "give its whole text as written (notice.png)"} and cam.keys == ["right"]
    assert "is independent" in capsys.readouterr().out               # an ordinary run prints it, to give it whole
    got = screens.pass_named_notice(cam, ROW, "different settings for", ROW, words=False)
    assert "refused" in got and capsys.readouterr().out == ""        # a run that withholds what it reads prints nothing


def test_a_line_outside_the_screen_box_is_judged_too(monkeypatch):
    got, keys = judged(monkeypatch, NOTICE + [line("Cancel", 600, x=300, w=60)])
    assert keys == [] and "refused" in got


def test_words_read_across_a_space_are_no_words_run_together(monkeypatch):
    plain = [line("Camera settings and lens end presets are kept", 100), line("in the next screen.", 140), OK_LINE]
    from proving import screens
    fake_ocr(monkeypatch, plain)
    cam = NoticeCamera()
    cam.press("right")
    phrase = "camera settings and lens end presets are kept in the next screen"
    assert screens.pass_named_notice(cam, ROW, phrase, ROW) == {"row": ROW, "frame": "notice.png"}
    for joined_up in ("Deleteall", "SettingReset", "Formatthe"):
        got, keys = judged(monkeypatch, SENTENCE + [line(joined_up, 220), OK_LINE])
        assert keys == [] and got.get("refused", "").startswith("it reads as a confirmation, its words run together"), \
            (joined_up, got)


def test_the_runtime_check_refuses_a_confirmation_whatever_the_phrase(monkeypatch):
    """A phrase the parse would refuse ("delete all", a confirmation's words), given straight to the judgement: the
    notice is still refused on the camera, nothing pressed."""
    from proving import screens
    fake_ocr(monkeypatch, [line("Delete all", 100), OK_LINE])
    cam = NoticeCamera()
    cam.press("right")
    got = screens.pass_named_notice(cam, ROW, "delete all", ROW)
    assert got == {"refused": "it reads as a confirmation (notice.png)"} and cam.keys == ["right"]


def test_no_notice_for_its_ok_or_an_ok_not_reached_is_no_pass(monkeypatch):
    from proving import screens
    from proving.base import Failed
    fake_ocr(monkeypatch, NOTICE)
    monkeypatch.setattr(screens, "info_notice_ok", lambda *a, **k: None)
    cam = NoticeCamera()
    cam.press("right")
    assert screens.pass_named_notice(cam, ROW, PHRASE, ROW) == {"refused": "no notice was up for its OK (notice.png)"}

    def failed(*a, **k):
        raise Failed("the notice's OK could not be reached")
    monkeypatch.setattr(screens, "info_notice_ok", failed)
    assert screens.pass_named_notice(cam, ROW, PHRASE, ROW) == {"refused": "its OK could not be taken (notice.png)"}
    assert cam.keys == ["right"]


# ---------------------------------------------------------------------------------------------- the parse (runner)

def test_the_parse_takes_one_row_and_the_notices_whole_text(capsys):
    import runner
    got = parsed(INFO)
    assert got == {ROW: PHRASE} and runner.notice_words(WORDS) == PHRASE      # punctuation and the glyph left out
    assert ROW in capsys.readouterr().out
    assert parsed() == {} and capsys.readouterr().out == ""          # no flag: nothing said
    assert parsed(f"{ROW}=  You  can set (different)   settings. ")[ROW] == "you can set different settings"
    assert parsed(INFO, rows=[ROW, "ISO"]) == got
    assert runner.info_ok_for(got, ROW.upper()) is got[ROW] and runner.info_ok_for(got, "ISO") is None
    assert runner.info_ok_for({"Set for Still": got[ROW]}, ROW) is None             # whole, never a part of the name


@pytest.mark.parametrize("value,rows,said", [
    (ROW, None, "ROW=PHRASE"),                                         # no "="
    (f"={WORDS}", None, "ROW=PHRASE"),                                 # no row
    (f"{ROW}=", None, "ROW=PHRASE"),                                   # no words
    (f"Nowhere Row={WORDS}", None, "no row label the kit knows"),     # a row the definition and page model lack
    (f"Format={WORDS}", None, "never opened"),                         # an action
    (f"Initialize={WORDS}", None, "never opened"),
    (f"Bluetooth Function={WORDS}", None, "never opened"),             # a network setting (a decision opens it to look)
    (f"Language={WORDS}", None, "never opened"),                       # identity
    (f"Access Authen. Info={WORDS}", None, "never opened"),            # credentials
    (f"Audio Signals={WORDS}", None, "never opened"),                  # sound
    (f"Network > Wi-Fi Direct Info. > {ROW}={WORDS}", None, "never opened"),   # a never-open label on the path
    (f"Format > Something={WORDS}", None, "never opened"),             # the first label of the path never-open
    (f"WPS Push={WORDS}", None, "never opened"),                       # never-open as written (safety.path_refused)
    (f"DeleteAll={WORDS}", None, "never opened"),                      # never-open, its words run together
    (f"SettingReset={WORDS}", None, "never opened"),
    (f"ScreenReader={WORDS}", None, "never opened"),
    (f"AudioSignals={WORDS}", None, "never opened"),
    (f"Steady.Shot={WORDS}", None, "never opened"),
    (f"{ROW}=.*", None, "as written"),                                 # a pattern's own signs: never a pattern
    (f"{ROW}=(?:.*e){{12}}", None, "as written"),
    (f"{ROW}=(?:[a-z ]+)+zyou can set different", None, "as written"),
    (f"{ROW}=you can set different settings|.", None, "as written"),
    (f"{ROW}=you can set different settings ^ here", None, "as written"),
    (f"{ROW}=Do you want to keep these settings?", None, "asks a question"),
    (f"{ROW}=Keep these settings？", None, "asks a question"),
    (f"{ROW}=you can set (", None, "at least 3 words"),                # signs are ignored: 3 words, 9 letters
    (f"{ROW}=different settings.", None, "at least 3 words"),
    (f"{ROW}=settings", None, "at least 3 words"),
    (f"{ROW}=differentsettingsforstillimagemode", None, "at least 3 words"),
    (f"{ROW}=set it now", None, "at least 3 words"),                   # 3 words, 8 letters
    (f"{ROW}=delete all images on the card", None, "no notice passed may say"),
    (f"{ROW}=you can restore the settings later", None, "no notice passed may say"),   # safety.confirmation alone
    (f"{ROW}=you can copy the settings later", None, "no notice passed may say"),      # safety.screen_refused alone
    (INFO, ["ISO"], "not one of the rows named with --rows"),
])
def test_the_parse_refuses_before_anything_connects(value, rows, said):
    with pytest.raises(SystemExit, match=re.escape(said)):
        parsed(value, rows=rows)


def test_the_parse_judges_each_refusal_on_its_own():
    """Each check of the parse refuses where no other does."""
    import runner
    from camkit import safety
    assert safety.path_refused(["Format", "Something"]) and not safety.never_open("Format > Something")
    assert safety.path_refused(["WPS Push"]) and runner.run_together_refused("WPS Push") is None
    assert runner.run_together_refused("DeleteAll") and not safety.path_refused(["DeleteAll"])
    assert runner.run_together_refused("SettingReset") and not safety.path_refused(["SettingReset"])
    assert runner.run_together_refused("ScreenReader") and not safety.path_refused(["ScreenReader"])
    # never-open once its sign is left out, by the guards' own patterns, not by a name written out plainly
    assert runner.run_together_refused("Steady.Shot") and not safety.path_refused(["Steady.Shot"])
    assert all(re.sub(r"[^a-z0-9]", "", n) not in "steadyshot" for n in runner._never_open_words())
    assert runner.run_together_refused(ROW) is None
    for phrase, confirms, refused in (("you can restore the settings later", True, False),
                                      ("you can copy the settings later", False, True)):
        assert bool(safety.confirmation(phrase)) is confirms and bool(safety.screen_refused(phrase)) is refused


# the a1 II's rows whose names hold a never-open name read across two words, or as a word alone: none is run together
ACROSS = ["Av/Tv Rotate", "Crop Level", "Delete confirm.", "Delete pressing twice", "FTP Transfer Func.",
          "FTP Transfer Status", "File Format", "File Name Format", "Pre-Capture Settings", "Px Proxy File Format",
          "Rating Set(Custom Key)", "Time Code Format", "Time Code Preset", "User Bit Preset", "Zoom Ring Rotate"]


def test_names_read_across_words_are_no_words_run_together():
    import runner
    from camkit import safety
    assert [r for r in ACROSS if safety.path_refused(r.split(" > ")) or runner.run_together_refused(r)] == []
    assert list(runner.info_ok_or_exit([f"{r}={WORDS}" for r in ACROSS], labels=set(ACROSS))) == ACROSS
    for r in ("DeleteAll", "SettingReset", "Formatthe", "AutoCreateStillImage"):
        assert runner.run_together_refused(r), r
    assert runner.joined("camera settings, presets and lens end", ["erase", "reset", "send"]) is None
    assert runner.joined("Deleteall", ["delete"]) == "delete" and runner.joined("Alldata", ["all data"]) == "all data"
    assert runner.joined("the word deleted", ["delete"]) is None and runner.joined("presets", ["reset"]) is None


def test_the_parse_takes_the_definitions_row_labels_by_default(monkeypatch):
    import runner
    monkeypatch.setattr(runner, "definition", lambda: {"menu": [{"tab": "Setup", "group": "G", "label": ROW}]})
    assert list(runner.info_ok_or_exit([INFO])) == [ROW]
    monkeypatch.setattr(runner, "definition", lambda: {})
    with pytest.raises(SystemExit, match="no row label the kit knows"):
        runner.info_ok_or_exit([INFO])


def test_a_row_named_twice_is_refused():
    with pytest.raises(SystemExit, match="named twice"):
        parsed(INFO, f"{ROW.lower()}=the setting set for is independent")


def test_the_runners_refuse_the_flag_where_it_has_no_place(monkeypatch, tmp_path):
    import crawl_run
    import prove_run
    the_map = tmp_path / "map.json"
    the_map.write_text(json.dumps({"rows": [{"path": [ROW], "kind": "checklist", "options": []},
                                            {"path": ["ISO"], "kind": "list", "options": []}]}), encoding="utf-8")
    monkeypatch.setattr(prove_run.proving.base, "MAP", prove_run.proving.base.MAP)        # put back after the test
    for argv, said in ((["prove_run", "--info-ok", INFO], "--info-ok passes a notice for the checklist rows named "
                                                          "with --rows only"),
                       (["prove_run", "--info-ok", INFO, "--rows", ROW, "--network"],
                        "--info-ok passes no notice on a --network run"),
                       (["prove_run", "--info-ok", INFO, "--rows", ROW, "--help-text"],
                        "--info-ok passes no notice with --help-text"),
                       (["prove_run", "--info-ok", INFO, "--rows", "ISO", "--map", str(the_map)],
                        "not one of the rows named with --rows"),
                       (["prove_run", "--info-ok", f"Nowhere Row={WORDS}", "--rows", "Nowhere Row", "--map",
                         str(the_map)], "no row label the kit knows")):
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit, match=re.escape(said)):
            prove_run.main()
    monkeypatch.setattr(sys, "argv", ["crawl_run", "--info-ok", INFO, "--network"])
    monkeypatch.setattr(crawl_run, "load_scan", lambda scan: pytest.fail("the scan was loaded"))
    with pytest.raises(SystemExit, match="--network"):
        crawl_run.main()


def test_prove_run_passes_a_notice_before_a_checklist_only():
    import prove_run
    named = parsed(INFO)
    assert prove_run.info_ok_jobs_or_exit([{"path": [ROW], "kind": "checklist"}, {"path": ["ISO"], "kind": "list"}],
                                          named) is None
    with pytest.raises(SystemExit, match="before a checklist only"):
        prove_run.info_ok_jobs_or_exit([{"path": [ROW], "kind": "list"}], named)


# ---------------------------------------------------------------------------------------------- the checklist prover

def prove(tmp_path, monkeypatch, named, lines=NOTICE):
    """proving.checklists' prover on a NoticeCamera, its seams faked; returns (the camera, the proof lines, the error)."""
    from proving import checklists
    fake_ocr(monkeypatch, lines)
    for name, value in (("place", lambda cam: "here"), ("same_place", lambda a, b: True),
                        ("to_row", lambda cam, *a, **k: cam.press("menu")), ("after_download", lambda cam, done: None),
                        ("finish_attempt", lambda *a, **k: None), ("vlm_option", lambda cam: "OK"),
                        ("on_box", lambda cam, labels, box: cam.where == "checklist" and cam.cursor == box),
                        ("check_state", lambda cam: cam.ticks[cam.cursor] if cam.where == "checklist"
                         and cam.cursor < len(BOXES) else None),
                        ("focused_button", lambda cam: "OK" if cam.where == "checklist" and cam.cursor == len(BOXES)
                         else ""),
                        ("lit_text", lambda image, path: ROW if Path(path).name == "row.png" else ""),
                        ("camset", SimpleNamespace(read=lambda p: None, diff=lambda a, b: [])),
                        ("INFO_OK", named)):
        monkeypatch.setattr(checklists, name, value)
    cam, out = NoticeCamera(tmp_path), io.StringIO()
    link = SimpleNamespace(download=lambda tag: tmp_path / f"{tag}.DAT")
    job = {"path": [ROW], "kind": "checklist", "labels": BOXES}
    err = None
    try:
        checklists.prove_check_row(cam, link, Run("pass2", root=tmp_path), job, tmp_path / "base.DAT", out)
    except checklists.Failed as e:
        err = e
    return cam, [json.loads(x) for x in out.getvalue().splitlines()], err


def test_the_checklist_prover_passes_the_named_notice_on_every_visit(tmp_path, monkeypatch):
    cam, proofs, err = prove(tmp_path, monkeypatch, parsed(INFO))
    assert err is None and cam.keys[:2] == ["right", "enter"]
    assert [p["label"] for p in proofs] == BOXES + ["(all back)"]
    assert all(p["info_ok"] == {"row": ROW, "passed": True, "frame": "notice.png"} for p in proofs)
    assert cam.keys.count("right") == len(proofs)                  # one notice a visit, one Enter on each
    assert cam.ticks == [False] * len(BOXES)                         # every box put back
    assert "independent" not in json.dumps(proofs).lower()           # the notice's words are kept nowhere


def test_without_the_flag_the_checklist_prover_fails_at_the_notice(tmp_path, monkeypatch):
    cam, proofs, err = prove(tmp_path, monkeypatch, {})
    assert err is not None and "Right opened notice" in str(err) and "enter" not in cam.keys and proofs == []


def test_the_checklist_prover_refuses_a_notice_not_the_one_named(tmp_path, monkeypatch):
    other = [line("This function is currently disabled.", 100), OK_LINE]
    cam, proofs, err = prove(tmp_path, monkeypatch, parsed(INFO), other)
    assert err is not None and "not passed" in str(err) and "enter" not in cam.keys and proofs == []


# ---------------------------------------------------------------------------------------------- the menu tree

@pytest.mark.parametrize("summary,greyed,state", [
    ({"outcome": "notice", "kind": "notice"}, False, ("info", "an information notice comes first")),
    ({"outcome": "notice (named, not passed: not the notice named (00012.png))", "kind": "notice"}, False,
     ("info", "an information notice comes first")),
    ({"outcome": "notice (named, not passed: x)", "kind": "notice"}, True, ("greyed", "")),
    ({"outcome": "walked", "kind": "checklist", "info_ok": {"row": ROW, "frame": "f.png"}}, False,
     ("walked", "an information notice comes first")),
    ({"outcome": "notice passed: a submenu screen after its OK, left unwalked", "kind": "submenu",
      "info_ok": {"row": ROW, "frame": "f.png"}}, False,
     ("unhandled", "an information notice comes first; notice passed: a submenu screen after its OK, left unwalked")),
    ({"outcome": "walked", "kind": "checklist"}, False, ("walked", "")),          # no notice: as before
    ({"outcome": "left for kit/table_walk.py", "kind": "table"}, False, ("unhandled", "left for kit/table_walk.py")),
])
def test_the_menu_tree_knows_the_notice_outcomes(summary, greyed, state):
    import menu_tree
    assert menu_tree.state_of(summary, greyed) == state
    row = menu_tree.row_of(ROW, summary, (ROW,), {})
    assert row["kind"] == ("notice" if summary["outcome"].startswith("notice (") or summary["outcome"] == "notice"
                           else summary["kind"])


# ---------------------------------------------------------------------------------------------- a new setting's tab

MENU = [{"tab": "Setup", "group": "Operation Customize", "label": ROW, "order": 223},
        {"tab": "Focus", "group": "Focus Area", "label": "Focus Area Limit", "order": 118},
        {"tab": "Shooting", "group": "My Menu", "label": "Twice", "order": 1},
        {"tab": "Setup", "group": "Other", "label": "Twice", "order": 2}]


def test_a_new_checklist_settings_tab_is_its_menu_rows(monkeypatch):
    import schema_update as S
    from camkit import camset
    assert S.menu_tab(MENU, ROW) == "Setup" and S.menu_tab(MENU, f"{ROW} [White Balance copies apart]") == "Setup"
    assert S.menu_tab(MENU, "Focus Area Limit > Something") == "Focus"
    assert S.menu_tab(MENU, "Nowhere") == "" and S.menu_tab(MENU, "Twice") == "" and S.menu_tab(None, ROW) == ""
    monkeypatch.setattr(S, "run_start", lambda: Path("start.DAT"))
    monkeypatch.setattr(camset, "read", lambda p: SimpleNamespace(
        get=lambda area, rid: SimpleNamespace(size=1, count=1) if area == 0 else None))
    s = S.new_setting("global:0x0182", ROW, {"Aperture: ticked": 1, "Aperture: unticked": 0}, MENU)
    assert s["tab"] == "Setup" and s["name"] == f"{ROW}: Aperture" and s["values"] == [[0, "Not ticked"], [1, "Ticked"]]
    assert S.new_setting("global:0x0182", ROW, {"Aperture: ticked": 1, "Aperture: unticked": 0})["tab"] == ""


def test_the_shipped_definitions_menu_gives_the_tabs_the_writer_gave_before():
    """The tabs a table in kit/schema_update.py gave new checklist settings before 2026-11-14 are the definition's menu's
    own: taking the menu's changes none."""
    import schema_update as S
    f = Path(__file__).resolve().parents[2] / "editor" / "definitions" / "ILCE-1M2_fw4.00.json"
    if not f.exists():
        pytest.skip("no shipped ILCE-1M2 definition")
    menu = json.loads(f.read_text(encoding="utf-8")).get("menu")
    before = {"Recognition Target": "Focus", "Reg. Flash Shooting Set": "Exposure/Color",
              "Rating Set(Custom Key)": "Playback", "DISP (Screen Disp) Set": "Setup", "Focus Area Limit": "Focus"}
    assert {r: S.menu_tab(menu, r) for r in before} == before
