"""Reading what the camera's screen shows: the label under the cursor bar (OCR, the vision model as the decider),
a carousel's title and its second axis's strip, a row found by its label, the cursor's place without text, and the
notices a choice can bring up (the camera's refusal, a one-time explanation, an information notice), each left with
MENU first and given its OK only where the camera refuses MENU and OK is its only button (camkit.live.leave_notice), or
where the run names it with --info-ok (pass_named_notice, pass_note), since 2026-11-14."""
import difflib
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from camkit import match, ocr, safety, screen
from camkit.live import info_ok_hint, info_ok_text, leave_notice
from camkit.vlm import PROMPTS, ask_role
from page_model import key_text, same_option, same_text
from runner import INFO_OK_SLACK, info_ok_for, joined, notice_words

from .base import Blocked, Failed

BAR_X = {"menu": (140, 470), "submenu": (55, 470), "list": (110, 556),   # label crops, as in pass 1
         "picker": (370, 636)}                                            # the function picker, right of its radio

# The notices a run names with --info-ok ({row: the phrase's words}, runner.info_ok_or_exit), whichever runner takes the
# flag (kit/prove_run.py, kit/provers/mode_switch.py, afreg_run.py, framepos_run.py): pass_note and the checklist prover
# (proving.checklists.INFO_OK, the same dict) pass a notice before a row's screen only as it names it
INFO_OK: dict = {}
# The rows whose own question (safety.ROW_QUESTIONS: Exposure Std. Adjust's on the a1 II) a run's --allow answers with
# OK (runner.row_questions_or_exit), whichever runner takes the flag (kit/crawl_run.py, kit/prove_run.py): only
# pass_row_question answers it, on that row's path alone; every other row's notice is left as ever
ROW_QUESTION: set = set()


def refuse_or_fail(cam, name: str, what: str):
    """Right did not open the row's screen. The camera's own refusal ("not available as follows Gamma
    HLG2": PP10's Black Gamma, 2026-10-29) is left as a notice the kit does not answer is left (leave_notice: MENU, and
    OK only where the camera refuses MENU there and OK is its only button) and raised as Blocked; anything else is
    Failed."""
    s = cam.read()
    if s.kind == "notice":
        text = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
        if re.search(r"not available", text, re.I) and not safety.confirmation(text):
            reason = re.sub(r"\s+", " ", text.split("as follows", 1)[-1])
            reason = re.sub(r"[\s•●]*(\bOK\b)?[\s•●]*$", "", reason).strip()     # the OK button and its dot
            reason = re.sub(r"^\W+", "", reason)                             # an icon read as "%"
            leave_notice(cam)                   # MENU; OK back to the row only where MENU is refused (the a1 II's)
            raise Blocked(f"{name}: blocked by {reason!r}", reason)
    raise Failed(f"{name}: Right opened {s.kind}, {what}")


def screen_text(cam) -> str:
    """All the text OCR reads on the frame on show."""
    return ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))


def lit_icon_label(frame) -> str:
    """The lit bar's label read with the icon at its start painted over, as camkit.crawl.icon_entry reads a row
    (camkit.screen.label_icons finds the icon by its pixels, page_model.covered_readings reads the label right of it):
    "" where no bar is lit, the bar starts with no icon, or the reading fails."""
    from camkit.live import lit_found
    from page_model import MENU_LABEL, SUBMENU_LABEL, covered_readings
    try:
        box, _ = lit_found(frame.image)
        if not box:
            return ""
        column = MENU_LABEL if box[0] > 100 else SUBMENU_LABEL        # a menu page's bar starts at 138, a submenu's at 56
        band = (box[1], box[3])
        boxes, text_x = screen.label_icons(frame.image, band, column[0])
        if not boxes:
            return ""
        got = covered_readings({0: (frame.image, {0: (band, boxes, text_x)})}, column, {"ocr": None})
        return str((got.get(0, {}).get(0) or {}).get("ocr") or "")
    except Exception:
        return ""


def bar_is_row(lit: str, row: str, frame=None) -> bool:
    """Whether the lit bar read `lit` (on `frame`, the frame before Right) is the row `row`: safety.bar_on_row on the lit
    text, as everywhere; or, where an icon stands at the bar's start (lit_icon_label, measured 2026-11-21 on Exposure
    Std. Adjust in the Movie and S&Q menus, read "SExposure Std. Adjust": kit2_crawl_expstd_mv 00013_down), the bar's
    label read with the icon covered passes bar_on_row, and the lit text is that reading with one token of at most
    camkit.row_names.ICON_LEAD characters in front (the icon's letters, glued on or set apart). The bar must still be the
    row: nothing is taken because it contains the row's name."""
    from camkit.row_names import ICON_LEAD
    if safety.bar_on_row(lit, row):
        return True
    if frame is None:
        return False
    covered = lit_icon_label(frame)
    if not covered or not safety.bar_on_row(covered, row):
        return False
    seen, label = safety.plain(lit or ""), safety.plain(covered)
    k = seen.find(label, 1)
    lead = seen[:k].strip() if k > 0 else ""
    return bool(lead) and " " not in lead and len(lead) <= ICON_LEAD and safety.bar_on_row(seen[k:], row)


def _reads_ok(lit) -> bool:
    return safety.fold(lit or "").strip().casefold() == "ok"


def pass_row_question(cam, name: str, lit_before: str, before=None) -> dict | None:
    """The question a row asks before it opens, answered with OK on the run's word for that row alone (--allow ROW, the
    owner's word: ROW_QUESTION; Exposure Std. Adjust on the a1 II, 2026-11-21). None where the row (`name`'s last label)
    is not one the run named: its notice is the caller's, as ever. Otherwise Enter goes out once, and only when all hold:
    the screen is a notice; the lit bar read before Right (`lit_before`, on the frame `before`) is the row (bar_is_row:
    safety.bar_on_row, or its label right of an icon drawn before it); the screen's
    whole text is that row's own question (safety.row_question: its words as measured on the camera's frames, its two
    buttons OK and Cancel, nothing else); and OK is lit, after at most one Up, which moves the cursor from Cancel onto OK
    above it (nothing is chosen by it). The press carries ("row_question", ROW), so the camera's own Enter check judges it
    again on the screen read afresh (camkit.live's row_question_passed). Returns {"row", "frame", "by"} once passed, else
    {"refused": why}, no Enter sent (the caller leaves the notice with MENU, which cancels the row's opening)."""
    row = name.split(" > ")[-1]
    if row not in ROW_QUESTION:
        return None
    frame = cam.frame.path.name
    if cam.read().kind != "notice":
        return {"refused": f"not a notice ({cam.read().kind}, {frame})"}
    if not bar_is_row(lit_before, row, before):
        return {"refused": "the lit bar read before Right is not the row named"}
    why = safety.row_question(screen_text(cam), row)
    if why:
        return {"refused": f"not {row}'s own question ({why}, {frame})"}
    if not _reads_ok(notice_lit(cam)):
        cam.press("up")                     # the cursor from Cancel onto OK, above it: a move, nothing chosen
        if cam.read().kind != "notice" or not _reads_ok(notice_lit(cam)):
            return {"refused": f"OK could not be lit on {row}'s question ({cam.frame.path.name})"}
    cam.confirm_once = ("row_question", row)
    cam.press("enter")
    return {"row": name, "frame": frame, "by": f"--allow {row!r}"}


def to_notice_ok(cam) -> None:
    """The cursor off a notice's "Don't show this again." box onto its OK (Down, at most twice), never ticking the box: a
    tick would be a setting changed for a proof. Moves the cursor only."""
    for _ in range(2):
        if not re.search(r"don.?t show", notice_lit(cam) or "", re.I):
            return
        cam.press("down")


def info_screen(cam) -> bool:
    """Whether the screen on show is one pass_note and pass_named_notice may pass: a notice, or a first-time screen read
    as no known kind (it draws no notice's frame lines) with a "Don't show this again." line (dont_show), Custom
    Key/Dial Set.'s on the a1 II (safety.first_time_screen judges it so at the press)."""
    kind = cam.read().kind
    if kind == "notice":
        return True
    return kind == "unknown" and any(dont_show(ln) for ln in ocr.read([cam.frame.path])[cam.frame.path])


def notice_before(cam, row: str, lit_before: str = "", words: bool = True) -> dict | None:
    """After Right on the row `row` ("A > B"): the screen the camera shows before the row's own, when it is one a run may
    pass (a first-time screen with "Don't show this again." and OK, Custom Key/Dial Set.'s after a settings reset: "In
    the next setting screen, you can check the function assigned to a specific button by pressing that button on the
    device", 2026-11-07; or any notice where --info-ok names the row), passed as pass_note passes it; None for any other
    screen, left as it is (a refusal notice is its caller's). Returns pass_note's answer."""
    if not info_screen(cam):
        return None
    if info_ok_for(INFO_OK, row) is None:
        text = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
        if not re.search(r"show this again", text, re.I) or safety.confirmation(text):
            return None
    return pass_note(cam, row, lit_before, words)


def first_time_notice(cam, row: str | None = None, lit_before: str = "") -> bool:
    """notice_before as a yes or no: True once a first-time screen (or the notice --info-ok names for `row`) is passed
    and the screen behind it opens; False for any other screen, left as it is, or one not passed (MENU on it cancels the
    row's opening). The box is never ticked."""
    got = notice_before(cam, row or "", lit_before)
    return got is not None and "refused" not in got


def pass_note(cam, row: str, lit_before: str, words: bool = True) -> dict:
    """A notice that Right on `row` opened before the row's own screen (Mode Dial Control Set's note, a first-time
    screen with "Don't show this again.": info_screen), its OK taken so the screen behind it opens: only as the run
    names it with --info-ok (INFO_OK; pass_named_notice judges it, the lit bar read before Right as the row), or where
    the camera refuses MENU on it and OK is its only button (leave_notice, after the cursor is taken off a "Don't show
    this again." box: to_notice_ok). MENU on a notice the camera takes cancels the opening: the row is not passed, and
    the message gives the --info-ok that names it, its text as read (info_ok_text). With `words` False (a run whose
    notices may name another setting's value, decision 16: afreg_run's and framepos_run's setup, a --network prove
    run) the text is never printed nor put in the message: it goes to the run's events.jsonl alone ("notice_not_passed",
    with the row and the frame; on a --network or --owner run only what safety.notice_kept keeps of it), and the message
    names the frame and the row and says where the text is. Returns {"row", "frame", "by"} once passed, else
    {"refused": why}."""
    frame = cam.frame.path.name
    phrase = info_ok_for(INFO_OK, row) if row else None
    if phrase is not None:
        got = pass_named_notice(cam, row, phrase, lit_before, words)
        return got if "refused" in got else {**got, "by": "--info-ok"}
    if not info_screen(cam):
        return {"refused": f"not a notice ({cam.read().kind}, {frame})"}
    said = info_ok_text(cam)                # read on the notice's own frame, before any press moves it
    to_notice_ok(cam)
    if leave_notice(cam) == "menu":
        return {"refused": f"the notice ({frame}) took MENU, which cancels it: its OK goes only where --info-ok names it "
                           f"or where the camera refuses MENU on it; {info_ok_hint(cam, row, frame, said, words)}"}
    return {"row": row, "frame": frame, "by": "a lone OK after MENU was refused"}


# An option drawn grey (the camera's own greyed state: Color Mode's entries with Gamma on HLG, 2026-11-19), told as
# camkit.screen._page_rows tells a greyed menu row: the 95th percentile of the text's pixels (grey above GREY_INK, not
# orange) on the option's own line, ~120 on a greyed entry and ~225 on a white one, the lit bar's included (kit2_pass2
# 260193-260368: 118-134 grey, 225-245 white); within GREY_TELL of GREY_LINE either way, or with fewer than GREY_MIN
# such pixels, it cannot be told
GREY_INK, GREY_LINE, GREY_TELL, GREY_MIN = 60, 170, 20, 150
OPTION_X = {"list": BAR_X["list"], "sidelist": (305, 595)}      # an option's text, beside its radio or scroll bar


def drawn_grey(cam) -> tuple:
    """(whether the option under the cursor is drawn grey: True, False, or None where it cannot be told; the measure,
    or None) on the screen on show: on a list or side list by GREY_LINE's rule on its lit bar's band (6 px in from
    either edge), on a carousel by its lit icon's red (icon_grey); None on any other screen, or a list without a bar."""
    s = cam.read()
    if getattr(cam.frame, "image", None) is None:
        return None, None
    if getattr(s, "kind", None) == "dialog":
        return icon_grey(cam.frame.image)
    bar = getattr(s, "bar", None)
    if getattr(s, "kind", None) not in OPTION_X or not bar:
        return None, None
    return _grey_band(cam.frame.image, s.kind, *bar)


# A carousel's lit option, told grey by its icon in the column at the left, the one icon drawn red: bright where the
# camera takes the option, dim dark red where it greys it (kit2_pass2 119966 against 119947). The measure is the 95th
# percentile of the red of the column's reddish pixels (red over ICON_INK, 40 over green and blue); on the first camera's
# carousel proof frames it read 102-124 on all 13 options the camera refused (Flash Mode's and ISO's, two rows alone)
# and 209-255 on all 221 it applied (kit/tools/reader_census.py --variants grey counts it again, 2026-11-20); between
# ICON_GREY and ICON_WHITE, or with fewer than ICON_MIN such pixels, it cannot be told
CAROUSEL_COLUMN = (0, 40, 108, 410)             # x0, y0, x1, y1: the column of icons, left of its rule
ICON_INK, ICON_GREY, ICON_WHITE, ICON_MIN = 90, 145, 185, 100


def icon_grey(image) -> tuple:
    """(whether a carousel's lit option is drawn grey, by its icon's red: True, False or None; the measure or None)."""
    x0, y0, x1, y1 = CAROUSEL_COLUMN
    a = np.asarray(image)[y0:y1, x0:x1].astype(np.int16)
    if a.ndim != 3 or a.shape[2] < 3:
        return None, None
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    red = r[(r > ICON_INK) & (r > g + 40) & (r > b + 40)]
    if len(red) < ICON_MIN:
        return None, None
    p = float(np.percentile(red, 95))
    return (True if p <= ICON_GREY else False if p >= ICON_WHITE else None), p


def _grey_band(image, kind: str, t: int, b: int) -> tuple:
    """GREY_LINE's rule on one option's band of a list or side list (t, b: its top and bottom, 6 px in from each):
    (True, False or None, the measure or None)."""
    x0, x1 = OPTION_X[kind]
    g, o = screen._grey(image)[t + 6:b - 6, x0:x1], screen._orange(image)[t + 6:b - 6, x0:x1]
    ink = g[(g > GREY_INK) & ~o]
    if len(ink) < GREY_MIN:
        return None, None
    p = float(np.percentile(ink, 95))
    if p <= GREY_LINE - GREY_TELL:
        return True, p
    if p >= GREY_LINE + GREY_TELL:
        return False, p
    return None, p


# where a list's and a side list's options stand: from the top of the first to the bottom of the last a screen can
# draw (camkit.screen's LIST_SCROLL and SIDE_SCROLL tracks), one bar's height and 4 px apart (sidelists.from_neighbours)
OPTION_Y = {"list": (screen.LIST_SCROLL[2], screen.LIST_SCROLL[3]), "sidelist": (screen.SIDE_SCROLL[1], screen.SIDE_SCROLL[2])}


def grey_rows(cam) -> list:
    """[(top, bottom, lit, drawn grey: True, False or None, the measure or None)] for each option band of the list or
    side list on show, top to bottom: the lit bar's, and the bands a bar's height and 4 px apart above and below it
    inside OPTION_Y, each by drawn_grey's rule (an empty band measures None). [] on any other screen or without a bar.
    What the census judges a reader's whole-list answer by (kit/tools/reader_census.py, variant "entries")."""
    s = cam.read()
    bar = getattr(s, "bar", None)
    if getattr(s, "kind", None) not in OPTION_X or not bar or getattr(cam.frame, "image", None) is None:
        return []
    t, b = bar
    pitch = b - t + 4
    top, bottom = OPTION_Y[s.kind]
    bands = [(t + j * pitch, b + j * pitch) for j in range(-12, 13)]
    return [(y0, y1, j == 12, *_grey_band(cam.frame.image, s.kind, y0, y1))
            for j, (y0, y1) in enumerate(bands) if y0 >= top - 6 and y1 <= bottom + 6]


def frame_lines(cam) -> list:
    """OCR's lines of the whole frame on show (a notice after OK: proving.commit reads it here)."""
    return ocr.read([cam.frame.path])[cam.frame.path]


def bar_text(cam) -> str:
    """OCR of the label under the cursor bar (menu row, submenu row, list option)."""
    s, f = cam.read(), cam.frame
    if not s.bar or s.kind not in BAR_X:
        return ""
    x0, x1 = BAR_X[s.kind]
    pad = -2 if s.kind == "list" else 0
    t = ocr.text_in(ocr.read([f.path])[f.path], (x0, s.bar[0] - pad, x1, s.bar[1] + pad)).strip(" •")
    return re.sub(r"\s+[oO0]$", "", t)              # the radio circle OCR reads as a letter


def option_key(t: str) -> str:
    """Option labels compared without case, spaces, dots or OCR look-alikes, keeping a leading
    number and a decimal point between digits (camkit.match.key: "F1.1" is never F11). A Cyrillic look-alike
    is its Latin letter ("С.Temp./Filter", 2026-10-31). The rules live in camkit/match.py."""
    return match.key(t)


def main_name(label: str, kind: str) -> str:
    """A carousel option's name without its second-axis value ("Continuous Shooting: Mid" ->
    "Continuous Shooting"): the value shown depends on what was chosen there last."""
    return label.split(":", 1)[0] if kind == "dialog" else label


def carousel_text(cam) -> str:
    """OCR of the orange line under a carousel's title: the option under the cursor (pass 1's crop)."""
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], (110, 60, 636, 112)).strip()


def _matches(t: str, labels) -> list:
    """The labels a reading names: by option_key, then without a radio circle read in front, then by same_option. A
    reading that may have lost the decimal point telling two labels apart (match.lost_point: "13\\"" beside 1.3" and
    13") names both, a doubt each caller takes as no one option (the reader asked, else no choice), as before
    option_key kept the point."""
    if match.lost_point(t, labels):
        return [i for i, l in enumerate(labels) if match.loose(l) == match.loose(t)]
    hits = [i for i, l in enumerate(labels) if option_key(l) == option_key(t)]
    if not hits:        # the saved option's radio circle read as a letter in front ("03" for "3")
        t2 = re.sub(r"^[oO0]\s*", "", t)
        hits = [i for i, l in enumerate(labels) if t2 != t and option_key(l) == option_key(t2)]
    if not hits:        # an icon read as letters in front ("SAF..."); never between near-twins (0.7 / 0.07 s)
        hits = [i for i, l in enumerate(labels) if same_option(t, l)]
    return hits


def option_answer(cam) -> dict | None:
    """The vision model's whole answer about the option under the cursor on the frame on screen (PROMPTS["option"]:
    "title", "selected", "value"); None when the reader fails or answers anything but an object. kit/provers/
    scale_run.py reads a scale's number from it, which can come in "value" with "selected" empty (2026-11-10)."""
    try:
        v = ask_second(cam.frame.path.read_bytes(), PROMPTS["option"], timeout=25)
    except Exception:
        return None
    return v if isinstance(v, dict) else None


def vlm_option(cam) -> str:
    """The vision model's reading of the option under the cursor (its answer's "selected", option_answer): the decider
    where OCR is unsure (short numbers, lost signs), and a second reading kept with every proof (user, 2026-10-29: use
    vLLM all the time if it makes sense; ~1 s a call)."""
    v = option_answer(cam)
    return str(v.get("selected") or "") if v else ""


# one worker: a proof's evidence question goes out while the run goes on (Enter, the download, the wait after it); the
# questions that decide a press never come here and are asked in line, as before
_EVIDENCE = ThreadPoolExecutor(max_workers=1, thread_name_prefix="evidence")


class Later:
    """A proof's evidence reading, the one kept in its "vlm" field and never deciding a press: `read` (the prover's
    vlm_option) asked on a worker thread about the frame on show when it was made (its own frame object, so the frame
    the run shows next is never the one read), joined by result() before the proof line is written. The answer is the
    one read(cam) gives in line: the reader's failure is its empty answer, said once in the run by the reader
    (camkit.vlm.failing), as before, and so is anything read raises (option_answer takes every failure for no answer),
    so that the line is written. The speed review of 2026-11-18: the evidence question cost 0.8-1.1 s a proof with the
    reader free, 5-8 s with it slow, all of it waited."""

    def __init__(self, read, cam, pool=None):
        self._future = (pool or _EVIDENCE).submit(read, SimpleNamespace(frame=cam.frame))

    def result(self):
        try:
            return self._future.result()
        except Exception:
            return ""


def later(read, cam, pool=None) -> Later:
    """read(cam) (a prover's vlm_option) asked in the background about the frame on show now (Later), on `pool` (a
    lap's, lap_workers) or the one evidence worker."""
    return Later(read, cam, pool)


# A lap that asks the reader about every entry it passes, where the answer only names the entry (kit/provers/
# mymenu_run.py's picker lap), keeps up to this many questions out at once, on workers of its own: no more than the
# second reader's server takes ("parallel" in its private/config.json entry; the a1 II's vLLM server takes 8)
LAP_WORKERS = 4


def lap_workers() -> int:
    """How many questions a lap keeps out at once: the "parallel" of the reader playing the second role (a stand-in's
    where one plays it), at most LAP_WORKERS; 1 where it cannot be told."""
    try:
        from camkit import vlm
        return max(1, min(int(vlm.playing("second").get("parallel") or 1), LAP_WORKERS))
    except Exception:       # noqa: BLE001 (no reader, a config that cannot be read: one at a time)
        return 1


def settled(v):
    """v's answer where it is a Later (waited for), else v as it is: what a proof line keeps in its "vlm" field."""
    return v.result() if isinstance(v, Later) else v


# A carousel's title line redraws a moment after its side strip (ISO, 2026-10-29), so it was read after a fixed 0.4 s
# and a fresh grab, twice per option. With HDMI eyes it is now read once its strip has stopped changing (TITLE_QUIET),
# having changed from the frame the press was made on where that press stepped within the carousel (a Down: the
# title must change), or after a still TITLE_OPEN_QUIET where it opened it (the title's change from the menu page
# says nothing). TITLE_LATE, the deadline, read as it is then, as before: today's 0.4 s plus the 2.9 s the speed
# review measured as the 99th percentile of a carousel Down's change on live-preview carousels, plus one quiet window
# (0.2 s). A second reading with no press or grab between them takes the first one's frame, waiting nothing.
TITLE_BOX = (110, 60, 636, 112)
TITLE_QUIET = 0.15
TITLE_OPEN_QUIET = 0.4
TITLE_LATE = 3.5
_TITLED: list = []                  # the frame the last title wait settled on


def title_settled(cam, tag: str = "reread") -> bool:
    """The carousel's title ready to read on the camera's frame (see TITLE_BOX). With HDMI eyes: True where the frame
    on show is the one the last such wait settled on (no press, no grab since), nothing waited; else the strip watched
    (HdmiSource.settle_box) and the frame it settled on taken (refresh(frame=)), False. With other eyes 0.4 s and a
    fresh grab every time, as before (the OSD picture lags: a later grab can show more), False."""
    eyes = getattr(cam, "hdmi", None)
    if getattr(eyes, "name", "") == "hdmi" and hasattr(eyes, "settle_box"):
        if _TITLED and _TITLED[0] is getattr(cam, "frame", None):
            return True
        prior = getattr(cam, "pressed_from", None)
        within = prior is not None and screen.read(prior).kind == cam.read().kind
        f, _ = eyes.settle_box(TITLE_BOX, prior.image if within else None,
                               quiet=TITLE_QUIET if within else TITLE_OPEN_QUIET, timeout=TITLE_LATE)
        cam.refresh(tag, frame=f)
        _TITLED[:] = [cam.frame]
        return False
    time.sleep(0.4)
    cam.refresh(tag)
    return False


def box_answer(cam, timeout: float = 25.0) -> tuple:
    """(the text inside the lit box of a row of boxes, as the second reader reads it (PROMPTS["box"]: one "value"),
    the configured name of the reader that answered, whether it stands in for the second reader): kit/provers/
    optboxes_run.py's question about Zebra Level's Custom boxes, where vlm_option's "item under the cursor" is the list's
    lit option. The value is None where the reader fails, says no box is orange ({"value": null}), or answers anything
    but an object with one non-empty "value" (no guess is made of it)."""
    return _one_answer(cam, "box", "value", timeout)


def word_answer(cam, timeout: float = 25.0) -> tuple:
    """(the name the camera writes above a row of boxes for its lit box, as the second reader reads it (PROMPTS
    ["box_word"]: one "word"), the reader's configured name, whether it stands in): kit/provers/optboxes_run.py's
    question where OCR's reading of that name is not plain Latin, or empty. None as box_answer gives it."""
    return _one_answer(cam, "box_word", "word", timeout)


def _one_answer(cam, prompt: str, field: str, timeout: float) -> tuple:
    """The second reader's one string `field` about the frame on show, asked PROMPTS[prompt]: (it, the reader's name,
    whether it stands in), it None where the reader fails, answers null or anything but one non-empty string."""
    from camkit import vlm
    try:
        v = ask_second(cam.frame.path.read_bytes(), PROMPTS[prompt], timeout=timeout)
    except Exception:
        v = None
    value = v.get(field) if isinstance(v, dict) else None
    try:
        who, standing = str(vlm.playing("second").get("name") or ""), vlm.standing_in("second") is not None
    except Exception:
        who, standing = "", False
    return (value.strip() if isinstance(value, str) and value.strip() else None), who, standing


def ask_second(image: bytes, prompt: str, timeout: float) -> dict:
    """The "second" reader's answer; when it will not connect, the next configured reader that answers takes the
    role for the rest of the run: camkit.vlm.ask_role, through which every question a run asks about a frame goes
    (camkit.live asks it so too)."""
    return ask_role("second", image, prompt, timeout)


# A carousel option's second axis drawn as a strip of cells under the dialog's body, between its ◂ ▸ (screen.GLYPHS'
# strip_left and strip_right): Focus Area's Spot sizes and Custom 1-3 as filled cells, the lit one orange with dark
# text, and Tracking's areas as an icon with the size or "C1" after it, the lit one drawn orange (the a1 II:
# runs/<model>_fw<fw>/kit2_afreg2 00204_reread.png and 00206_reread.png, kit2_axes 00341_reread.png). Five places
# 87.5 px apart with the lit cell in the middle one; the cells right of it are the values Right comes to next, in
# turn, and those left of it the values Left does (a short list leaves the places past its ends empty). The lit cell is
# looked for in AXIS_STRIP, the cells' text read on the line AXIS_TEXT_Y (a frame's corner drawn in the strip, above or
# below the text, stays out: kit2_afreg2 00206, kit2_axes 00320)
AXIS_STRIP = (158, 322, 597, 394)
AXIS_TEXT_Y = (347, 368)
AXIS_PITCH = 87.5
# the short text a value's cell shows: "Spot: L" and "Tracking: Spot L" show "L" (the axis walk's "Tracking: SpotS"
# shows "S"), "Custom 3" and "Tracking: Custom 3" show "C3"; Wide, Zone, Center Fix and Expand Spot show an icon alone
CELL_SIZE = re.compile(r"(?:spot\s*)?(xs|s|m|l|xl)", re.I)
CELL_CUSTOM = re.compile(r"custom\s*(\d)", re.I)
# a reading that is a cell's short text alone: after the cell's icon read as signs ("#C1", "••• M", "®*ХS"), with a dot
# after it ("XL."), Cyrillic look-alikes ("СЗ") and "(" for C ("(1", RapidOCR); never with a letter before it or a sign
# after it ("EСЗ", or "L ]": Center Fix's [ ] read as an L, kit2_axes 00356_right.png)
CELL_TEXT = re.compile(r"[^A-Z0-9]*(C[1-9]|XS|XL|S|M|L)[\s.]*")
CELL_LOOKALIKES = str.maketrans("СсЗзХхМмЅѕ(", "CC33XXMMSSC")


def cell_code(label) -> str | None:
    """The short text an axis value's cell shows ("Custom 3" -> "C3", "Tracking: Spot L" -> "L"); None for a value
    whose cell is an icon alone."""
    tail = str(label or "").split(":", 1)[-1].strip()
    if m := CELL_SIZE.fullmatch(tail):
        return m[1].upper()
    m = CELL_CUSTOM.fullmatch(tail)
    return f"C{m[1]}" if m else None


def cell_text_code(text) -> str | None:
    """The cell's short text a reading of it is (CELL_TEXT), or None."""
    m = CELL_TEXT.fullmatch(str(text or "").translate(CELL_LOOKALIKES).upper())
    return m[1] if m else None


def axis_lit_x(image) -> float | None:
    """Centre x of the axis strip's lit cell: its orange (screen's mask, closed as camkit.live closes a lit item's, so a
    cell's fill, or its letters and icon, are one region), the regions within a cell's width of the largest; None when
    no orange there could be a cell (a strip greyed with its option, kit2_afreg2 00300_reread.png, draws its lit cell
    dark red), or orange of note lies outside that cell."""
    import cv2
    from camkit.live import CLOSE
    x0, y0, x1, y1 = AXIS_STRIP
    o = screen._orange(image)[y0:y1, x0:x1].astype(np.uint8)
    closed = cv2.morphologyEx(o, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, CLOSE))
    n, lab, st, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    regions = [(int(st[i, 0]), int(st[i, 0] + st[i, 2]), int(o[lab == i].sum())) for i in range(1, n)]
    regions = [r for r in regions if r[2] >= 8]                 # a speck: a frame's corner blended over a cell
    if not regions:
        return None
    big = max(regions, key=lambda r: r[2])
    cell = [r for r in regions if max(r[1], big[1]) - min(r[0], big[0]) <= 0.7 * AXIS_PITCH]
    lit = sum(r[2] for r in cell)
    if lit < 40 or sum(r[2] for r in regions if r not in cell) > 0.25 * lit:
        return None
    return x0 + (min(r[0] for r in cell) + max(r[1] for r in cell)) / 2


def axis_cells(f, lit_x: float) -> list:
    """[(reader, text, offset)]: each reading of a strip cell's short text alone (cell_text_code) on frame f, by the
    configured OCR engine and the second one where installed, with its place counted from the lit cell (0 the lit one,
    1 the next right, -1 the next left); a reading off the cells' text line or between two places is left out."""
    x0, _, x1, _ = AXIS_STRIP
    out = []
    for eng in [ocr.engine()] + ([ocr.second()] if ocr.second() else []):
        for ln in ocr.read([f.path], eng=eng)[f.path]:
            cx, cy = ln.x + ln.w / 2, ln.y + ln.h / 2
            if not (x0 <= cx <= x1 and AXIS_TEXT_Y[0] <= cy <= AXIS_TEXT_Y[1]) or ln.w > 1.2 * AXIS_PITCH:
                continue
            k = round((cx - lit_x) / AXIS_PITCH)
            if abs(cx - lit_x - k * AXIS_PITCH) <= 0.3 * AXIS_PITCH and abs(k) <= 2 and cell_text_code(ln.text):
                out.append((eng, ln.text, k))
    return out


def strip_value(cam, vals: list, title: str, vlm: str = "") -> tuple:
    """(index into vals or None, how it was read) of the axis value the strip's lit cell shows, for a title that names
    none ("Customß 7": the Custom 3 box's corner drawn over the title, kit2_pass2 234940_reread.png and kit2_afreg2
    00206_reread.png). Only when the title still reads as the option's (it starts as every value does: "custom",
    "spot:", "tracking:"), so a Custom cell's "C3" is never Tracking's "Tracking: Custom 3", and the strip has its lit
    cell (axis_lit_x). Each reading of a cell's short text (axis_cells, and the vision model's reading, which often is
    the lit cell's: "C3") names a value, and with its place one for the lit cell: "C2" one left of it is the value after
    Custom 2, Custom 3. Every reading must name the same one, and none a short text no value of the axis has; how is
    {"read_by": "axis cell", "cell_readings": [{"reader", "text", "offset"}]}, else {}. An axis whose cells are all
    icons, as most are, is never read so (nothing is read off its frame)."""
    codes = {}
    for j, v in enumerate(vals):
        if c := cell_code(v):
            codes.setdefault(c, []).append(j)
    lead = os.path.commonprefix([option_key(v) for v in vals])
    if not codes or len(lead) < 3 or not option_key(title).startswith(lead):
        return None, {}
    lit_x = axis_lit_x(cam.frame.image)
    if lit_x is None:
        return None, {}
    readings = axis_cells(cam.frame, lit_x) + ([("vlm", vlm, 0)] if cell_text_code(vlm) else [])
    named = set()
    for _, text, k in readings:
        js = codes.get(cell_text_code(text)) or []
        if len(js) != 1:
            return None, {}                 # a short text the axis does not have, or has twice: not this strip
        named.add((js[0] - k) % len(vals))
    if len(named) != 1:
        return None, {}
    return named.pop(), {"read_by": "axis cell",
                         "cell_readings": [{"reader": r, "text": t, "offset": k} for r, t, k in readings]}


SEEN: dict = {}                  # row label -> how OCR reads it on the camera ("Fixed Speed SBY" for STBY)


def keeps_lead(reading: str, label: str) -> bool:
    """A label's short first word ("Av", "Tv") must be in the reading too: label cleaning drops it as
    an icon, so "Tv Auto/Manual Switch" passed for "Av Auto/Manual Switch" and the Tv proofs were
    made on the Av row (2026-10-31). An icon glued on in front still passes ("SAF Frame" for "AF Frame").
    Before a bracket the camera may drop the space: "Lo(E-Shutter)" for "Lo (E-Shutter)" (2026-11-01)."""
    m = re.match(r"([A-Za-z0-9]{1,2})\s+(?=[A-Z(])", (label or "").strip())
    return m is None or re.search(rf"{re.escape(m.group(1).lower())}[\s(]", (reading or "").lower()) is not None


def glued(label: str) -> str:
    """A short first word glued to its bracket, as the camera shows it: "Lo (E-Shutter)" is
    "Lo(E-Shutter)" on screen, and label cleaning drops a short word before a space as an icon, which
    left "(e-shutter)" for all four speed rows (2026-11-01)."""
    return re.sub(r"^([A-Za-z0-9+]{1,3})\s+\(", r"\1(", (label or "").strip())


LIT_ROWS_ALIKE = 2      # rows read alike on both frames, outside the two bars, that make the frame before the same page


def _rows_outside(lines, x0, x1, bands) -> dict:
    """{row centre's y in 10 px steps: text} of the OCR lines in the label column (x0..x1) outside every band."""
    out = {}
    for ln in lines:
        cy = ln.y + ln.h / 2
        if x0 <= ln.x + ln.w / 2 <= x1 and not any(t <= cy <= b for t, b in bands):
            out[round(cy / 10)] = safety.plain(ln.text)
    return out


def lit_letter(cam, prev) -> str:
    """The lit bar's label where OCR reads none on it (a lone white letter on the orange bar, which Apple Vision drops:
    Color Depth's M and Y, kit2_pass2 304086 and 304087, 2026-11-21), resting on TWO signs that agree, else "": the
    label OCR read at the bar's place on the frame before (`prev`: the cursor moved one row), on the same page (every
    row both frames read outside the two bars reads alike, at least LIT_ROWS_ALIKE of them; a row one frame did not read
    is no difference), AND the second reader's label for the lit bar (camkit.live.reader_label: the "second" role alone,
    never the third readers). Where OCR reads the bar, or either sign is missing, or they differ: ""."""
    from camkit import live as camlive
    s = cam.read()
    bar = getattr(s, "bar", None)
    if prev is None or not bar or s.kind not in BAR_X or bar_text(cam):
        return ""
    x0, x1 = BAR_X[s.kind]
    try:
        before = screen.read(prev)
        now_lines = ocr.read([cam.frame.path])[cam.frame.path]
        before_lines = ocr.read([prev.path])[prev.path]
    except Exception:
        return ""
    if getattr(before, "kind", None) != s.kind:
        return ""
    bands = [bar] + ([before.bar] if getattr(before, "bar", None) else [])
    now_rows, before_rows = _rows_outside(now_lines, x0, x1, bands), _rows_outside(before_lines, x0, x1, bands)
    both = set(now_rows) & set(before_rows)
    if len(both) < LIT_ROWS_ALIKE or any(now_rows[y] != before_rows[y] for y in both):
        return ""
    was = ocr.text_in(before_lines, (x0, bar[0], x1, bar[1])).strip(" •")
    said, _why = camlive.reader_label(cam.frame.path)
    if not was or not said or safety.plain(was) != safety.plain(said):
        return ""
    return was


def at_label(cam, kind, label, prev=None) -> bool:
    """Whether the bar on the `kind` screen reads as `label`; where OCR reads nothing on the lit bar, its label by
    lit_letter's two agreeing signs, given the frame before (`prev`, find_row's)."""
    if cam.read().kind != kind:
        return False
    t = bar_text(cam) or (lit_letter(cam, prev) if prev is not None else "")
    return (same_text(t, glued(label)) and keeps_lead(t, label)) or (label in SEEN and same_text(t, SEEN[label]))


def closest_row(texts: list, label) -> int | None:
    """The one reading in a lap of rows that is clearly the label's: the only one ending with the
    whole label (its icon read as a word in front: "uir Rear Dial R", too close to "t7Rear Dial L" by
    ratio, 2026-10-31), else the closest when clearly closer than every other."""
    k = key_text(label)
    ends = [i for i, t in enumerate(texts) if len(k) >= 4 and key_text(t).endswith(k) and len(key_text(t)) - len(k) <= 4]
    if len(ends) == 1:
        return ends[0]
    score = sorted(((difflib.SequenceMatcher(None, key_text(t), key_text(label)).ratio(), i) for i, t in enumerate(texts)),
                   reverse=True)
    if not score or score[0][0] < 0.8 or (len(score) > 1 and score[0][0] - score[1][0] < 0.1):
        return None
    return score[0][1]


def place(cam) -> tuple:
    """Where the cursor is, without reading text: screen type, page (breadcrumb picture), cursor row.
    OCR reads some labels several ways ("Fixed Speed STBY" / "SBY" / "siBy", 2026-10-29)."""
    s = cam.read()
    return s.kind, screen.page_bits(cam.frame.image), s.row


def same_place(a, b, tol: int = 2) -> bool:
    """Same screen type and cursor row, page pictures within `tol` cells (packed bits)."""
    if a is None or b is None or a[0] != b[0] or a[2] != b[2]:
        return False
    return sum(bin(x ^ y).count("1") for pa, pb in zip(a[1], b[1], strict=True) for x, y in zip(pa.tobytes(), pb.tobytes(), strict=True)) <= tol


def run_tmp_png(f):
    """A frame grabbed without saving, written to a temporary file for OCR (one per process: two runs at once never
    read each other's frame); the caller removes it once read."""
    import tempfile
    from PIL import Image
    path = Path(tempfile.gettempdir()) / f"camkit_notice_{os.getpid()}.png"
    Image.fromarray(f.image).save(path)
    return path


def notice_focus(img):
    """The notice's orange-filled bar (x, y, w, h), anywhere on the screen: its OK can sit below the
    band the menu readers look in (y 404-460 under a "Don't show this again." box)."""
    import cv2
    _, _, st, _ = cv2.connectedComponentsWithStats(screen._orange(img).astype(np.uint8), connectivity=8)
    bars = [(int(x), int(y), int(w), int(h)) for x, y, w, h, a in st[1:] if 40 <= h <= 66 and w >= 120 and a / (w * h) > 0.6]
    return max(bars, key=lambda b: b[2] * b[3]) if bars else None


def info_notice_ok(cam, name: str, kinds: tuple = ("notice", "unknown"), words: bool = True,
                   named: str = "") -> dict | None:
    """An information notice after a choice ("You can perform detailed settings ... Select on Cam &
    Send", with a "Don't show this again." box above its OK, after Send (This Image) on a playback Fn
    tile, 2026-10-29): the cursor taken to its OK (Down, never ticking the box), then left as a notice the kit does not
    answer is left (leave_notice: MENU, which on the a1 II closes it and the menu with it; OK only where the camera
    refuses MENU and OK is its only button), since 2026-11-14: OK straight away only where the screen's kind takes it (a
    list prover passes "table" for an information screen with buttons, Exposure Ctrl Type's) or the run names the
    notice with --info-ok (`named`, which pass_named_notice has judged: the camera judges it again, LiveCamera.press's
    notice_ok). Anything that reads like a confirmation, or a cursor that is not on OK, fails the cell. None when no
    notice is up (the screen is not one of `kinds`). Returns {"text", "frame", "left_by": "ok" or "menu"}. words
    False: what the screen reads is neither printed nor put in a failure's message (the frame is named; the caller
    keeps the words where it keeps a notice's), for a setup step whose screen can show the owner's values."""
    kind = cam.read().kind
    if kind not in kinds:
        return None
    lines = ocr.read([cam.frame.path])[cam.frame.path]
    text = ocr.text_in(lines, (0, 0, 640, 480))
    said = f": {text[:80]!r}" if words else ""
    if not text or safety.confirmation(text) or not re.search(r"\bOK\b", text):
        raise Failed(f"{name}: a notice came up ({cam.frame.path.name}){said}")
    frame = cam.frame.path.name
    for _ in range(3):
        focused = notice_lit(cam)
        if re.fullmatch(r"\W*OK\W*", focused or ""):
            if named or kind in safety.ENTER_KINDS:
                if words:
                    print(f"   information after the choice, taken with its OK: {text[:70]!r}", flush=True)
                cam.press("enter", **({"notice_ok": named} if named else {}))
                return {"text": text, "frame": frame, "left_by": "ok"}
            left = leave_notice(cam)
            if words:
                print(f"   information after the choice, {'closed with MENU' if left == 'menu' else 'taken with its OK (MENU refused)'}: "
                      f"{text[:70]!r}", flush=True)
            return {"text": text, "frame": frame, "left_by": left}
        if not re.search(r"don.?t show", focused or "", re.I):
            break
        cam.press("down")                    # off the "Don't show this again." box, never Enter on it
    raise Failed(f"{name}: the notice's OK could not be reached ({cam.frame.path.name}){said}")


def notice_lit(cam) -> str:
    """OCR of the notice's lit (orange-filled) bar on the frame on screen (notice_focus), "" when none is lit."""
    box = notice_focus(cam.frame.image)
    return ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path],
                       (box[0], box[1], box[0] + box[2], box[1] + box[3])) if box else ""


# a line of a notice that is a button's word alone (safety.BUTTON_WORDS), its dot or bullet aside: a notice passed with
# --info-ok has one, its OK
BUTTON_LINE = re.compile(r"[\s•●.]*(" + "|".join(sorted(safety.BUTTON_WORDS)) + r")[\s•●.]*", re.I)
# what no line of such a notice but its OK may say, in any reading of the line (safety.readings): a second button, read
# whole or not ("Cance1", "x Cancel", "Back"), its word whole (a button's word is no prefix of prose: "No" is no "not",
# "Start" no "starts", 2026-11-15), or a word of a choice or an action, inflected too ("Apply", "deleted",
# "overwritten", "Executed.")
NOT_BESIDE_OK = re.compile(r"canc|\b(?:yes|no|back|close|enter|start|return|stop|resume|retry|later|abort|quit|"
                           r"not now)\b|\b(?:execute|apply|register|proceed|continue|confirm|delete|format|reset|"
                           r"overwrit|eras|initiali[sz])")


def _confirm_names() -> tuple:
    """safety.confirmation's own words as written ("delete", "all data", "initialize" and "initialise", "reset"), for
    joined: the same list, never a copy of it."""
    out = []
    for word in re.sub(r"^\\b\(|\)\\b$", "", safety._CONFIRM_RE.pattern).split("|"):
        out += [word.replace("[sz]", "s"), word.replace("[sz]", "z")] if "[sz]" in word else [re.sub(r"s\?$", "", word)]
    return tuple(dict.fromkeys(out))


# safety.confirmation's words run together inside one word of the notice ("Deleteall", "Willbelost"; runner.joined, which
# takes no name read across two words: "camera settings", "presets", "lens end"). The guards' own run-together view
# (safety.confirmation_refused, safety.readings beyond safety.plain_view: 2026-11-14) takes every space out, so it reads
# those across words and would refuse ordinary prose; a notice's text is judged in the plain view and by this check
# (pass_named_notice), and the camera's own Enter check (camkit.live.LiveCamera.confirm_refused) still judges the notice
# with confirmation_refused at the press. confirmation's words, a superset of confirmation_refused's run-together ones.
CONFIRM_NAMES = _confirm_names()
# a "Don't show this again." box's line, word for word (word_cover's slips allowed), which the phrase need not name
DONT_SHOW_WORDS = ("don't", "show", "this", "again")
# what an icon glued to a line's first or last word is never taken for: letters that would negate it ("unset",
# "isnt" read without its apostrophe)
NEGATING_BEFORE, NEGATING_AFTER = frozenset({"un", "in", "im", "il", "ir", "no"}), frozenset({"n", "nt"})
OK_BAND = 4          # px: a line whose middle is lower than this above the OK line's top sits on or below the OK's band


def letters(word: str) -> int:
    """The letters and digits of a word (an apostrophe inside it is none)."""
    return sum(c.isalnum() for c in word)


def word_cover(w: str, t: str, edge: bool = False) -> int | None:
    """How many letters of the notice's word `t` the phrase's word `w` accounts for, or None when it is not that word: the
    word as it stands; for a word of four letters or more, one letter read for another, dropped or put in
    (safety.one_apart: that letter is not accounted for); or, for a word of two letters or more that is the first or the
    last of its line (`edge`, where an icon sits beside the text), the word with one or two letters or digits glued on
    before or after it, never ones that negate it (NEGATING_BEFORE, NEGATING_AFTER): those are not accounted for."""
    if t == w:
        return letters(w)
    if letters(w) >= 4 and safety.one_apart(t, w):
        return min(letters(t), letters(w)) - (len(t) == len(w))
    if edge and letters(w) >= 2 and 0 < len(t) - len(w) <= 2:
        glued = t[:len(t) - len(w)] if t.endswith(w) else t[len(w):] if t.startswith(w) else ""
        if glued.isalnum() and glued not in (NEGATING_BEFORE if t.endswith(w) else NEGATING_AFTER):
            return letters(w)
    return None


def dont_show(ln) -> bool:
    """Whether an OCR line is a "Don't show this again." box's line and nothing else (DONT_SHOW_WORDS, word by word,
    word_cover's slips allowed: "Dont show this again")."""
    got = notice_words(ln.text).split()
    return len(got) == len(DONT_SHOW_WORDS) and all(word_cover(w, t) is not None
                                                    for w, t in zip(DONT_SHOW_WORDS, got, strict=True))


def notice_cover(phrase: str, lines: list) -> tuple | None:
    """How the phrase's words (`phrase`, runner.notice_words) account for a notice's lines (OCR lines, its OK and its
    "Don't show this again." line left out): None when its words are not all found in the lines' words, in order (each by
    word_cover); else (the letters and digits of the lines left unaccounted for, why the phrase does not account for the
    notice, "" where it does). It does not where a word it skips has three letters or more (an icon is read as a letter or
    two: "Stop", "Later" or a sentence is no icon), or where a line that holds none of its words lies outside the lines
    that hold them (a mark or a stray letter stacked above the OK)."""
    seen = []                                       # (line, word, the line's first or last word)
    for k, ln in enumerate(lines):
        got = notice_words(ln.text).split()
        seen += [(k, t, j in (0, len(got) - 1)) for j, t in enumerate(got)]
    matched, covered, i = set(), 0, 0
    for w in phrase.split():
        while i < len(seen):
            got = word_cover(w, seen[i][1], seen[i][2])
            i += 1
            if got is not None:
                covered += got
                matched.add(i - 1)
                break
        else:
            return None
    left_over = sum(letters(t) for _, t, _ in seen) - covered
    if any(letters(t) >= 3 for j, (_, t, _) in enumerate(seen) if j not in matched):
        return left_over, "a word it does not name"
    held = {seen[j][0] for j in matched}
    top = min((lines[k].y for k in held), default=0)
    bottom = max((lines[k].y + lines[k].h for k in held), default=0)
    if any(not top <= ln.y + ln.h / 2 <= bottom for k, ln in enumerate(lines) if k not in held):
        return left_over, "a line outside its text"
    return left_over, ""


def pass_named_notice(cam, name: str, phrase: str, lit_before: str, words: bool = True) -> dict:
    """--info-ok (runner.info_ok_or_exit): the information notice Right opened on the row `name` ("A > B" for a submenu's
    row) taken with its OK, so the screen behind it opens (Different Set for Still/Mv on the a1 II: "You can set
    different settings for still image mode and movie mode in the next screen. The setting set for ☑ is independent.",
    a single OK, 2026-11-03). Only for a notice that explains and asks nothing, whose whole text the run gives
    (`phrase`, runner.notice_words: letters, digits and single spaces; punctuation and glyphs ignored in both). Enter goes
    out once, and only when all hold:
    - the screen is a notice, or a first-time screen read as no known kind with a "Don't show this again." line
      (info_screen);
    - the lit bar read before Right (`lit_before`) is the row's last label (safety.bar_on_row, or page_model.same_text
      with its short first word kept: keeps_lead);
    - the phrase's words are found in the notice's lines, in order (notice_cover), its OK line aside, and a line that
      says "Don't show this again." and nothing else (dont_show), unless the phrase names its words too;
    - no reading of the text holds a question mark;
    - it reads as no confirmation (safety.confirmation, and its words run together inside one word: runner.joined),
      names nothing the never-open list holds (safety.screen_refused) and nothing of identity or credentials
      (safety.identity_screen);
    - exactly one of its lines is a button's word alone, and that word is OK (BUTTON_LINE);
    - no other line names a second button, a choice or an action in any reading (NOT_BESIDE_OK), and none sits on or
      below the OK line's band (OK_BAND);
    - the phrase accounts for the whole notice (notice_cover): no word of three letters or more it skips, no line
      outside its text that holds none of its words, and at most runner.INFO_OK_SLACK of its letters and digits left over
      (an icon read as a letter or two, a slip), so no sentence or button the phrase does not name can ride along;
    - the lit button reads OK (notice_lit), or the box above it is lit, and info_notice_ok, which takes the cursor Down
      off the box (never ticking it) and judges OK lit, presses the Enter.
    Every reading judged is spaced as read (safety.plain_view: as read, folded, OCR's capital I as an l, slips undone):
    the guards' run-together view takes every space out of the text, so ordinary prose reads as what it never says ("a
    different screen" holds "ntsc", "camera settings" "erase", "You can change" "canc"; 2026-11-14), and words run
    together are judged inside one word alone (runner.joined). The camera's own Enter check judges the notice again at
    the press (camkit.live.LiveCamera.confirm_refused, given the run's --info-ok as its notice_ok: no question mark, OK
    plainly its only button, safety.lone_ok, and safety.confirmation_refused, its words run together too).
    Returns {"row", "frame": the notice's frame} once passed, else {"refused": why} with nothing pressed; no text read
    off the screen is in either. Where the phrase leaves more of the notice over, the notice's text is printed (`words`:
    False on a run that withholds what it reads), so that its whole text can be given."""
    frame = cam.frame.path.name
    if not info_screen(cam):
        return {"refused": f"not a notice ({cam.read().kind}, {frame})"}
    row = name.split(" > ")[-1]
    if not (safety.bar_on_row(lit_before, row) or (same_text(lit_before, row) and keeps_lead(lit_before, row))):
        return {"refused": "the lit bar read before Right is not the row named"}
    why = notice_refused(cam, phrase, words)
    if why:
        return {"refused": why}
    try:
        # the run's --info-ok, judged here: the camera judges the notice again at the press (LiveCamera's notice_ok)
        if info_notice_ok(cam, name, kinds=("notice", "unknown"), words=False, named=name) is None:
            return {"refused": f"no notice was up for its OK ({frame})"}
    except Failed:
        return {"refused": f"its OK could not be taken ({frame})"}
    return {"row": name, "frame": frame}


def notice_refused(cam, phrase: str, words: bool = True) -> str:
    """Why the notice on screen is not the one --info-ok names by its whole text `phrase` (runner.notice_words), or
    "": every check of pass_named_notice's but the row's own (the phrase accounts for the notice, no question mark, no
    confirmation nor never-open name nor identity, a single OK alone on its band, the lit button OK). kit/drive.py judges
    a notice its --info-ok names with it alone (its presses open no row before the notice). No text read off the screen
    is in the reason; `words` False prints none either."""
    frame = cam.frame.path.name
    if not info_screen(cam):
        return f"not a notice ({cam.read().kind}, {frame})"
    lines = ocr.read([cam.frame.path])[cam.frame.path]
    text = " ".join(ln.text for ln in lines).strip()

    def an_ok(ln) -> bool:
        m = BUTTON_LINE.fullmatch(ln.text or "")
        return bool(m) and m[1].lower() == "ok"
    said = [ln for ln in lines if not an_ok(ln)]
    aside = [ln for ln in said if not dont_show(ln)]
    cover = notice_cover(phrase, aside)
    if cover is None and len(aside) < len(said):
        cover = notice_cover(phrase, said)          # a phrase that names the box's words too
    if cover is None:
        return f"not the notice named ({frame})"

    def spaced(t) -> list:
        return safety.plain_view(safety.readings, t)
    if any(q in r for r in spaced(text) for q in "?？"):
        return f"it asks a question ({frame})"
    for check, why in ((safety.confirmation, "it reads as a confirmation"),
                       (lambda t: joined(t, CONFIRM_NAMES), "it reads as a confirmation, its words run together"),
                       (lambda t: safety.plain_view(safety.screen_refused, t), "it names what the never-open list holds"),
                       (lambda t: safety.plain_view(safety.identity_screen, t), "it names identity or credentials")):
        if check(text):
            return f"{why} ({frame})"
    buttons = [ln for ln in lines if BUTTON_LINE.fullmatch(ln.text or "")]
    if [BUTTON_LINE.fullmatch(ln.text)[1].lower() for ln in buttons] != ["ok"]:
        return f"not a single OK: {len(buttons)} button lines ({frame})"
    ok_line = buttons[0]
    others = [ln for ln in lines if ln is not ok_line]
    if any(NOT_BESIDE_OK.search(r) for ln in others for r in spaced(ln.text)):
        return f"a line beside its OK names a button, a choice or an action ({frame})"
    if any(ln.y + ln.h / 2 >= ok_line.y - OK_BAND for ln in others):
        return f"a line sits on or below its OK's band ({frame})"
    left_over, why = cover
    if why or left_over > INFO_OK_SLACK:
        if words:
            print(f"   the notice reads {text!r}: give its whole text as written with --info-ok", flush=True)
        return (f"the notice has {left_over} letters or digits beyond the phrase{f', {why}' if why else ''}: give its "
                f"whole text as written ({frame})")
    lit = notice_lit(cam) or ""
    if not re.fullmatch(r"\W*OK\W*", lit) and not re.search(r"don.?t show", lit, re.I):
        return f"the lit button is not OK ({frame})"         # on the box, the cursor goes Down to OK (info_notice_ok)
    return ""
