"""A menu row the camera draws grey: why, asked of the camera itself, Help first, then one Right for its notice (the
a1 II's owner, 2026-11-20, asked "Grey menu rows: let the kit press Right once for the camera's notice when Help gives
no reason?", answered "Yes to the 4", it being one of four; until then the kit asked only the camera's Help, which on
the a1 II says of a grey row "This function is currently disabled.": Framing Stabilizer's took three guessed camera
runs to learn that Touch Operation shuts it).

    line = greyrow.ask_why(cam, ["Framing Stabilizer"], seen=seen, tried=tried, labels=labels)

For one row, the cursor on it on a menu or submenu page, in this order, each step pressing nothing where it stops:
  0. A row the kit may not open or reach whatever its colour (closed: never-open, what acts as it opens, a format,
     delete or reset, a row above it not seen opened, a path typed with an older name the camera's ROW_NAMES renames)
     gets no key, Help's neither, as kit/help_run.py passes it over;
     nor does a lit bar that, read on the fresh frame, reads nothing or as such a row itself (bar_refused), whatever
     the path as typed said.
  1. Drawn grey now: the lit bar's label measured on a frame grabbed afresh, never the page scan's (row_grey: the
     options' rule, proving.screens' GREY_*, on the menu's label crop; kit2_help's 398 lit rows read 117-131 on the 55
     the camera greys and 221-247 on the 343 it does not). White, or unsure: nothing pressed.
  2. Help offered: drive.help_refused (a menu page whose footer draws the help button, decision 7). Not offered:
     nothing pressed, "help not offered".
  3. Help: help_run.guide (C4, the popup's In-Camera Guide alone, OK back onto the row); its title, text and frames are
     kept; the cursor must be back on the row, else the row fails.
  4. One Right, only where all of these hold: Help was read and gave no reason (reasonless: its last sentence, where
     the camera writes a grey row's state, is one of REASONLESS, and no sentence before it, the row's description, is
     written with a refusal's words, REASON_WORDS); the kit may open the row as it would if it were white (closed and
     open_refused: never-open, what acts as it opens, a format, delete or reset, a row this body has not been seen to
     open, whose first open is the crawl's procedure alone, camkit.first_open); no Right went on this row before in the
     run, however it was spelled (`tried`, by the row's keys, its labels folded: label_key; spent before the press,
     whatever follows); the lit row still the row and still drawn grey.
     camkit.live judges the Right as every opening press (the never-open check on the bar read just then).
  5. After the Right (after_right): a notice that asks nothing is read and left by camkit.live.leave_notice (MENU
     first; its OK only where the camera refuses MENU and OK is plainly its only button); a screen that asks (its text a
     confirmation, or a question mark) gets MENU, never an answer; any other screen (the row opened after all, whatever
     its kind) MENU alone, which must leave it on a menu page or the shooting screen; the shooting screen gets nothing;
     the camera's playback view ends the run (StopsRun), the session's close leaving it (proving.nav). No other key: no Enter but
     that lone OK, no second Right.

The line written (the module's outcomes, "right" whether the Right went out): what was read and pressed. The guide's and
the notice's words are Sony's and the camera's state: they stay in the run's folder (decision 13). The blocker a line
names (camkit.coverage.blocker_of: the row label, never its value, as the option provers' lines carry theirs,
proving.greyed) is a lead, the setting to try, never the values that grey the row: the value the camera held is the
owner's (decision 16). Those come only from runs where the kit set each value of the blocker itself from a known start
file and saw the row grey or white."""
import re

import numpy as np

from camkit import coverage, first_open, match, row_names, safety, screen
from camkit.live import leave_notice, lit_text, text_of
from camkit.screen import same_state

from .base import Failed
from .screens import BAR_X, GREY_INK, GREY_LINE, GREY_MIN, GREY_TELL, place, same_place

ROW_KINDS = ("menu", "submenu")
# The camera's sentences that say a function is shut and not why: a grey row's guide ends with one, after the row's own
# description, as a paragraph of its own (kit2_help: 63 of the 1,993 guides read, every one "This function is currently
# disabled.", which OCR read whole on all 63). Compared as the guide's last sentence, folded, case and spacing aside, a
# reader's slip in it forgiven (reads_as: "This tunction is currently disabled." on five rows, 2026-11-20); a text whose
# last sentence is not one of these counts as a reason, and no Right goes
REASONLESS = ("This function is currently disabled.",)
# the popup's OK button read along at a guide's end ("... disabled. OK", "•ОК" with Cyrillic letters)
FOOTER_OK = re.compile(r"[\s•·]*(?<![A-Za-z0-9])[Oo0][Kk](?![A-Za-z0-9])\W*$")
# how far a slip may move the sentence's length, spaces and dots aside (match.key): a letter read for another moves it
# none, one dropped or doubled one; words added before or after it move it further, and they may be a reason
SLIP_CHARS = 2
FOLLOWS = re.compile(r"not available as follows\b", re.I)
# words a refusal is written with, which no sentence of the a1 II's 1,993 guides holds before its last (one guide's
# "the subject cannot be recognized" says what a level does, and is no refusal): in a grey row's description they may
# be its reason, so no Right goes
REASON_WORDS = re.compile(r"not available|unavailable|invalid|disabled|as follows|"
                          r"cannot be (?:set|used|selected|changed|executed|operated)", re.I)
SENTENCE_END = re.compile(r"(?<=[.!?。])\s+")

PASSED, NOT_GREY, UNSURE, NO_HELP, REASON, HELP_ONLY, TRIED, REFUSED, MOVED = (
    "passed over", "not drawn grey", "grey unsure", "help not offered", "help gave a reason", "help only",
    "right already pressed", "right refused", "no longer the grey row")
DRAWN_GREY = "drawn grey"   # a look's (look): white and unsure are NOT_GREY and UNSURE
LOOK = "look"               # a look's line's "kind"
NOTICE, QUESTION, OPENED, NO_RESPONSE, MENU_CLOSED, FAILED, PLAYBACK = (
    "notice", "question", "opened after all", "no response to right", "menu closed", "failed", "playback view")


class RowFailed(Failed):
    """The row failed: `line`, what was read and pressed on it before, the line the run writes for it."""

    def __init__(self, message: str, line: dict):
        super().__init__(message)
        self.line = line


class StopsRun(RowFailed):
    """The row left the camera where no run goes on: the camera's playback view after the Right, where a next row's
    MENU would open the menu over the view and its Downs and Rights go out in it. Its line is written, and the run goes
    up to the session's close, which leaves the view (proving.nav.to_shooting, leave_playback) before its restore."""


class PlaybackView(Failed):
    """after_right met the camera's playback view, nothing pressed there."""


def _say(message: str) -> None:
    print(message, flush=True)


def row_grey(cam) -> tuple:
    """(whether the lit row of the menu or submenu page on show is drawn grey: True, False, or None where it cannot be
    told; the measure, or None): the 95th percentile of the label's text pixels on the lit bar (grey above GREY_INK,
    not orange), as proving.screens.drawn_grey tells an option, on the page's label crop (BAR_X)."""
    s = cam.read()
    bar, image = getattr(s, "bar", None), getattr(cam.frame, "image", None)
    if getattr(s, "kind", None) not in ROW_KINDS or not bar or image is None:
        return None, None
    x0, x1 = BAR_X[s.kind]
    t, b = bar
    g, o = screen._grey(image)[t + 6:b - 6, x0:x1], screen._orange(image)[t + 6:b - 6, x0:x1]
    ink = g[(g > GREY_INK) & ~o]
    if len(ink) < GREY_MIN:
        return None, None
    p = float(np.percentile(ink, 95))
    return (True if p <= GREY_LINE - GREY_TELL else False if p >= GREY_LINE + GREY_TELL else None), p


def lit_of(cam) -> str:
    """The lit bar's text as OCR reads it (camkit.live.lit_text), "" where nothing is lit."""
    return lit_text(cam.frame.image, cam.frame.path)


def read_text(cam) -> str:
    """The whole screen's text as OCR reads it (camkit.live.text_of)."""
    return text_of(cam)


def on_row(lit: str, label: str) -> bool:
    """The lit bar's text `lit` reads the row `label`, an OCR slip allowed (help_run.on_label, after the page scan's
    position check or the submenu's find_row has said which row it is). Loose on purpose: what the bar is, is judged
    first, on its own text (bar_refused)."""
    from help_run import on_label
    return bool(str(lit or "").strip()) and on_label(lit, label)


def bar_label(lit: str, label: str) -> str | None:
    """The row's label as the lit bar draws it now: `label` where the bar's text, folded (safety.plain), is that label
    alone or before what is no letter or digit of a longer word (its value), with an icon's letters in front of it (a
    leading token of at most camkit.row_names.ICON_LEAD characters) or not, as camkit.first_open.Seen.lit_row tells a
    bar's label; None where the bar reads another label, or nothing."""
    seen, want = safety.plain(lit), safety.plain(label)
    if not seen or not want:
        return None
    token, _, rest = seen.partition(" ")
    for text in (seen, rest if 0 < len(token) <= row_names.ICON_LEAD else ""):
        if text.startswith(want) and not text[len(want):len(want) + 1].isalnum():
            return label
    return None


def bar_refused(lit: str, path, seen) -> str:
    """Why the lit bar, as read now, may not be opened, or "": a bar that reads nothing (the never-open check cannot judge
    it), a never-open text (safety.never_open), or one the look lap's own list refuses (safety.look_lap_refused: what
    never opens, the Screen Reader, a row whose opening acts, a format, delete or reset not seen opened). The path as
    typed is no proof of the bar: "Create New Fold" passes closed(), the bar it lands on reads Create New Folder."""
    if not str(lit or "").strip():
        return "the lit row reads nothing, so the never-open check cannot judge it"
    why = safety.never_open(lit)
    if why:
        return f"the lit row reads as never-open ({why})"
    why = safety.look_lap_refused(lit, bool(first_open.drawn(seen)(path)))
    if why:
        return f"the lit row: {why}"
    return ""


def _plain(text) -> str:
    return " ".join(safety.fold(str(text or "")).split()).strip().rstrip(".。").lower()


def reasonless(text) -> bool:
    """Whether a grey row's guide gives no reason: read (some text), its last sentence one of REASONLESS as a reader
    may slip in it (reads_as; the popup's OK read along left out, FOOTER_OK), and no sentence before it written with a
    refusal's words (REASON_WORDS: "not available as follows" among them, the refusal the camera names a blocker with)."""
    t = FOOTER_OK.sub("", " ".join(safety.fold(str(text or "")).split())).strip()
    parts = [p for p in SENTENCE_END.split(t) if p.strip()]
    if not parts or any(REASON_WORDS.search(p) for p in parts[:-1]) or FOLLOWS.search(parts[-1]):
        return False
    return any(reads_as(parts[-1], x) for x in REASONLESS)


def reads_as(reading, sentence) -> bool:
    """Whether a reading is `sentence` as a reader may have slipped in it: the same once folded (_plain), or one the
    kit's likeness rule takes for it (camkit.match.same: its key, else a near spelling with the same last word) whose
    length, spaces and dots aside (match.key), is within SLIP_CHARS of the sentence's, so no word is added to it."""
    a, b = _plain(reading), _plain(sentence)
    return a == b or (abs(len(match.key(a)) - len(match.key(b))) <= SLIP_CHARS and match.same(a, b))


def help_blocker(text, labels=()) -> dict | None:
    """The blocker a guide names, only from the refusal the kit knows ("not available as follows <row>":
    camkit.coverage.blocker_of on it, the row label, never its value), as proving.greyed.help_blocker; else None."""
    t = " ".join(str(text or "").split())
    m = FOLLOWS.search(t)
    return coverage.blocker_of(t[m.start():], labels) if m else None


def closed(path, seen, stored=None) -> str:
    """Why the kit may not open the row at `path` (labels from the top-level row) or reach it, whatever its colour, or
    "": the page model's stored never-open reason of its top-level row (`stored`), any label of the path never-open (safety.never_open: an
    action, a format, delete or reset, credentials, the camera's identity, a connection, a Wi-Fi or Bluetooth setting,
    sound, light or motion), or refused by the look lap's own list (safety.look_lap_refused: what never opens, the Screen
    Reader, a row whose opening acts, a format, delete or reset not seen opened), or a row above it this body has not
    been seen to open, which reaching it would open, or a path typed with a name the camera's ROW_NAMES renames
    (an older name: ask by the camera's). No run's --allow lifts any of these here. Every "seen" here is
    first_open.drawn's, the records under the labels the camera draws now: no row is seen through an older name
    (camkit.row_names)."""
    drawn = first_open.drawn(seen)
    camera = row_names.renamed(path)
    if tuple(camera) != tuple(str(x) for x in path):
        return (f"{' > '.join(map(str, path))!r} is an older name of {' > '.join(camera)!r} (ROW_NAMES): ask by the "
                "camera's name, the one every safety check judges")
    if stored:
        return f"never-open ({stored})"
    for i, label in enumerate(path):
        why = safety.never_open(label)
        if why:
            return f"never-open ({why})"
        why = safety.look_lap_refused(label, bool(drawn(path[:i + 1])))
        if why:
            return why
    above = [tuple(path[:i]) for i in range(1, len(path)) if not drawn(path[:i])]
    if above:
        return (f"{' > '.join(above[0])!r} is not seen opened on this body: its first open is the crawl's procedure "
                "(camkit.first_open), and reaching the row would open it")
    return ""


def open_refused(path, lit: str, seen, stored=None) -> str:
    """Why the Right may not go on the row at `path`, as an open of it would not if it were white, or "": closed(), the
    lit bar as read now judged the same way (never-open, the look lap's list), a bar that reads nothing, and the row
    itself not seen opened on this body (its first open is the crawl's procedure, camkit.first_open, which this run does
    not make). Every reason only refuses."""
    why = closed(path, seen, stored) or bar_refused(lit, path, seen)
    if why:
        return why
    drawn_as = bar_label(lit, path[-1])
    if drawn_as is None:
        return f"the lit row {str(lit).strip()!r} does not read as {path[-1]!r}, so its seen cannot be judged as drawn"
    if not first_open.drawn(seen)((*path[:-1], drawn_as)):     # the label the bar draws, as written in the records
        return ("not seen opened on this body: its first open is the crawl's procedure (camkit.first_open: RESTORE_BY_HAND "
                "before, the settings checked after), which this run does not make")
    return ""


def label_key(path) -> tuple:
    """The key a row's one Right is spent under by its labels: the path as the first-open procedure compares it
    (first_open.key: an older name ROW_NAMES gives the row renamed, each label folded by safety.plain), so "framing
    stabilizer" is Framing Stabilizer, and a row's older name and the camera's are one row for "never twice". Never a
    safety judgement's: those ask first_open.drawn."""
    return ("labels", *first_open.key(path))


def on_the_row(cam, path, seen, stored, line: dict, tag: str, say=_say) -> dict | None:
    """What ask_why and look check before anything else, nothing pressed: the row the kit may open and reach (closed)
    and the screen a menu page, then on a frame grabbed afresh (`tag`, its frame noted in `line`) the lit bar judged
    (bar_refused) and read as the row (on_row). Returns the line of a row passed over, else None with the cursor known
    on the row; raises RowFailed (its line) where the screen or the lit row is not the row's."""
    name, label = " > ".join(path), path[-1]

    def failed(why: str):
        raise RowFailed(f"{name}: {why}", {**line, "outcome": FAILED, "why": why})
    why = closed(path, seen, stored)
    if why:                                     # no key at all, Help's neither (kit/help_run.py passes these over)
        say(f"{name}: passed over, nothing pressed: {why}")
        return {**line, "outcome": PASSED, "why": why}
    if cam.read().kind not in ROW_KINDS:
        failed(f"the screen is {cam.read().kind!r} ({cam.frame.path.name}), not the row's menu page")
    cam.refresh(tag)                            # drawn grey now, on a frame grabbed afresh
    line["row_frame"] = cam.frame.path.name
    if cam.read().kind not in ROW_KINDS:
        failed(f"after a fresh look the screen is {cam.read().kind!r} ({cam.frame.path.name}), not the row's menu page")
    lit = lit_of(cam)
    why = bar_refused(lit, path, seen)
    if why:                                     # the bar itself, before any key: no Help on it either
        say(f"{name}: passed over, nothing pressed: {why}")
        return {**line, "outcome": PASSED, "why": why}
    if not on_row(lit, label):
        failed(f"the lit row is not {label!r} ({cam.frame.path.name})")
    return None


def look(cam, path, *, seen, stored=None, say=_say) -> dict:
    """A look (kit/provers/greyrow_run.py --look): whether the row at `path` under the cursor is drawn grey, white or
    unsure now, on a frame grabbed afresh, nothing pressed on it, Help's neither, after the checks ask_why makes before
    its Help (on_the_row). Its line: {"kind": LOOK, "path", "outcome": DRAWN_GREY, NOT_GREY, UNSURE or PASSED, "grey":
    the measure, "row_frame"}; it spends no Right. A chain sets a blocker's value (kit/provers/mode_switch.py --set) and
    looks, value by value: the runs a hand table's inactive_when takes its values from (docs/REMAPPING_PLAYBOOK.md,
    Phase 3). Raises RowFailed (its line) as on_the_row does."""
    path = [str(x) for x in path]
    line = {"kind": LOOK, "path": path}
    passed = on_the_row(cam, path, seen, stored, line, "look-row", say)
    if passed is not None:
        return passed
    grey, measure = row_grey(cam)
    outcome = DRAWN_GREY if grey is True else NOT_GREY if grey is False else UNSURE
    say(f"{' > '.join(path)}: {outcome}{'' if measure is None else f' (its label reads {measure:.0f})'}, "
        f"{line['row_frame']}: nothing pressed on it")
    return {**line, "outcome": outcome, "grey": None if measure is None else round(measure, 1)}


def ask_why(cam, path, *, seen, tried: set, keys=None, stored=None, labels=(), say=_say) -> dict:
    """The module's procedure on the row at `path` under the cursor; returns the row's line (outcome, right, grey,
    help, after, notice, blocker, why). seen: camkit.first_open.Seen (seen, unseen); tried: the keys of the run's rows
    whose Right is spent; keys: the row's (by default its label_key; kit/provers/greyrow_run.py adds the row the page
    scan leads to), spent where any is in `tried`, all added to it before the press; stored: the page model's never-open
    reason of its top-level row; labels: the labels a blocker is named by (runner.blocker_labels). Raises
    RowFailed (its line) where the row fails; a STOP, a refusal other than the lit row's and a lost link go up as
    raised."""
    path = [str(x) for x in path]
    name, label = " > ".join(path), path[-1]
    keys = (label_key(path),) if keys is None else tuple(keys)
    line = {"path": path, "right": False}

    def failed(why: str):
        raise RowFailed(f"{name}: {why}", {**line, "outcome": FAILED, "why": why})
    passed = on_the_row(cam, path, seen, stored, line, "grey-row", say)
    if passed is not None:
        return passed
    grey, measure = row_grey(cam)
    line["grey"] = None if measure is None else round(measure, 1)
    if grey is not True:
        said = "drawn white" if grey is False else "whether it is drawn grey cannot be told"
        say(f"{name}: {said}{'' if measure is None else f' (its label reads {measure:.0f})'}: nothing pressed")
        return {**line, "outcome": NOT_GREY if grey is False else UNSURE}
    from drive import help_refused              # drive imports the provers: here, not at the top
    why = help_refused(cam.read().kind, cam.frame.image)
    if why:
        say(f"{name}: drawn grey, and Help is not offered ({why}): nothing pressed")
        return {**line, "outcome": NO_HELP, "why": why}
    from help_run import guide
    row_place, row_screen = place(cam), cam.read()
    say(f"{name}: drawn grey: the camera's Help on it, to read why")
    try:
        r = guide(cam, name)
    except Failed as e:
        failed(f"its Help could not be read: {e}")
    line["help"] = {k: r.get(k) for k in ("title", "text", "frames", "popup")}
    if not same_place(place(cam), row_place):
        failed(f"after its guide the cursor is not back on the row ({cam.frame.path.name})")
    text = r.get("text") or ""
    if not reasonless(text):
        b = help_blocker(text, labels)
        say(f"{name}: its Help gives a reason, or words the kit does not take for none: no Right")
        return {**line, "outcome": REASON, **({"blocker": b} if b else {})}
    refused = open_refused(path, lit_of(cam), seen, stored)
    if refused:
        say(f"{name}: its Help gives no reason; no Right: {refused}")
        return {**line, "outcome": HELP_ONLY, "why": refused}
    if any(k in tried for k in keys):
        say(f"{name}: its Help gives no reason; a Right went on this row before in the run: no second")
        return {**line, "outcome": TRIED}
    grey, measure = row_grey(cam)
    if not on_row(lit_of(cam), label) or grey is not True:
        say(f"{name}: after its Help the lit row is not the grey row any more ({cam.frame.path.name}): no Right")
        return {**line, "outcome": MOVED}
    tried.update(keys)                          # spent before the press: never a second, whatever follows
    say(f"{name}: its Help gives no reason: one Right, to read the camera's notice, not to choose")
    try:
        cam.press("right")
    except safety.RowRefused as e:              # the camera's own check refused it: nothing went out
        say(f"{name}: the Right was refused before it went out ({e})")
        return {**line, "outcome": REFUSED, "why": str(e)}
    line["right"] = True
    try:
        got = after_right(cam, name, row_screen, labels, say)
    except PlaybackView as e:
        raise StopsRun(f"{name}: {e}", {**line, "outcome": PLAYBACK, "why": str(e)}) from e
    except Failed as e:
        raise RowFailed(f"{e}", {**line, "outcome": FAILED, "why": str(e)}) from e
    return {**line, **got}


def after_right(cam, name: str, row_screen, labels=(), say=_say) -> dict:
    """What the one Right brought up, and how it was left (the module's step 5): {"outcome", "after": {"screen",
    "frame", "left_by", "then", "asks"}, "notice": {"text", "frame"}, "blocker"}. Raises Failed where MENU leaves a screen
    that is no menu page nor the shooting screen, or on the camera's playback view, nothing pressed there."""
    s, frame = cam.read(), cam.frame.path.name
    if s.kind in ROW_KINDS and same_state(s, row_screen):
        say(f"{name}: the Right changed nothing: nothing more pressed")
        return {"outcome": NO_RESPONSE, "after": {"screen": s.kind, "frame": frame}}
    if s.kind == "shooting":
        say(f"{name}: the Right closed the menu ({frame}): nothing more pressed")
        return {"outcome": MENU_CLOSED, "after": {"screen": s.kind, "frame": frame}}
    if s.kind == "playback":
        say(f"{name}: the Right brought up the camera's playback view ({frame}): nothing pressed there, the run ends")
        raise PlaybackView(f"the Right brought up the camera's playback view ({frame}): nothing pressed there")
    text = read_text(cam)
    asks = safety.confirmation_refused(text) or ("a question mark" if safety.question_mark(text) else None)
    if s.kind == "notice" and not asks:
        left = leave_notice(cam)
        b = coverage.blocker_of(text, labels)
        said = f"blocked by {b.get('row') or b.get('equipment') or 'a remote session'}" if b else "no blocker named"
        say(f"{name}: the camera's notice ({frame}): {said}; left with {left.upper()}")
        return {"outcome": NOTICE, "after": {"screen": "notice", "frame": frame, "left_by": left},
                "notice": {"text": text, "frame": frame}, **({"blocker": b} if b else {})}
    cam.press("menu")                           # a question: never answered; any other screen: MENU alone
    then = cam.read().kind
    out = {"outcome": QUESTION if asks else OPENED,
           "after": {"screen": s.kind, "frame": frame, "left_by": "menu", "then": then, **({"asks": asks} if asks else {})}}
    say(f"{name}: the Right brought up a {s.kind} screen ({frame})" + (f" that asks ({asks})" if asks else "")
        + f": left with MENU, now {then}")
    if then not in (*ROW_KINDS, "shooting"):
        raise Failed(f"MENU on the {s.kind} screen the Right brought up left a {then} screen ({cam.frame.path.name})")
    return out
