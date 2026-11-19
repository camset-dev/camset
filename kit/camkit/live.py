"""The walkers' camera interface (press / read) on the real camera: each press goes over the link
and the screen is read once it settles over HDMI. Every settled frame is saved and every press is
logged in the run's events.jsonl. A STOP file raises link.StopRequested at the next press.

LiveCamera.press is the one way a walker, a prover or drive.py presses, so the row check lives there too: a press
that opens the lit row (Right, Enter, the multi-selector's right or centre, however the key is spelled) on a menu or
submenu page is refused when the lit row's text is on the never-open list (safety.never_open), unless the run named
that row as one it may open (may_open: drive.py --allow, a dated owner decision) and the reason is one such a name can
lift. A Wi-Fi or Bluetooth setting, an address screen or an identity row is lifted only by a dated owner decision that
names the row, for a run given --network (network, safety.network_lifted; an address screen only where kit/drive.py
looks at one, screens). Once such a row is open it is looked at only: up, down and MENU go out, Enter only on an option
the decision names (options), never Right, Left or a dial, which can commit a carousel's or a panel's option
(inside_refused, safety.look_refused); on an address screen, or a screen naming identity or credentials (a pairing
screen: safety.identity_screen), MENU alone, and no reader is asked (camkit.vlm.HELD). The lock ends only when the
screen read right after a MENU (or such an Enter) is the shooting screen, or the page the row was opened from with its
lit bar on the row itself (network_left): never on a screen's kind alone, never on a later read, so a camera slow to
draw the row's list, a MENU the camera ignored, or a list or a popup misread as a menu page, keeps it. The row's own
screen read as the shooting screen before any MENU (Manage Paired Device's list, 2026-11-13) is judged as no known
kind, MENU alone, and from then on a frame read as the shooting screen ends the row only when the camera's own picture
says so too (menu_closed).
A row a dated owner decision names ("lifts": "owner", docs/decisions/0008) is opened only for kit/drive.py --owner, which
gives the camera that one row (owner): with Right alone, once per run, from a menu page (a Right on it lit on any other
screen is refused here too), and, for a row whose opening acts (safety.opens_acting), only as an armed press drive.py
allowed for that row (permit) and safety.arm_refused passes on this camera's own reading. Inside it only up, down, MENU
and Enter go out; an action's step, final step or confirmation, or a never-choose option, only so allowed and checked;
after an armed press, MENU alone (owner_done). On such a run every Enter also meets this camera's own NEVER_ENTER
(wiping_refused: Initialize, Reset Network Set., SSID/PW Reset). A row whose values are withheld (safety.BLANKED) takes
MENU alone, asks no reader, and the eyes write every frame of it black (withhold, camkit.frames' withheld). handed counts
the presses handed to the link, which drive.py says in its log of an armed press that failed.
It fails closed as drive.py does: when an orange bar is drawn but OCR reads no text in it, the vision reader is
asked once for the row's label (reader_label), and the label it gives is judged the same way; when it gives none, the
press is refused, since the never-open check cannot judge a row it cannot read (2026-11-08). The reader takes about a
second: where its frame is by then older than STALE_S, the press is judged again on a fresh frame, or refused where the
screen changed meanwhile (lit_by_reader).

The screen read last goes with every press and dial to the link, whose guards judge C4 on it (decision 7) and every key
but MENU on the shooting screen (decision 21: refused there unless the caller names the key for that press,
on_shooting). A screen read as no known kind whose frame is black (HDMI blanked: Auto Framing On in Movie mode) is
asked of the camera's own picture first (judged_screen), and judged as the shooting screen when that reads as one; when
that picture cannot be read, no key but MENU goes. A screen read as the shooting screen while the camera says it is in
Playback is its playback view, kind "playback" (reading, camkit.session.playback_kind), where the link lets no key but
MENU out, named or not (decision 21). A shooting screen that is drawn but read as another kind (a DISP
mode that draws no battery) is not caught: the kit presses on unknown screens on purpose (the memory slots read as one).
The screen judged is never one the camera has left behind this camera's back: the link counts what can move it (a
download, an upload, any press or dial), and when that count has moved since the last read, the screen is grabbed and
read afresh before the press is judged (_fresh: a refresh, never a refusal).
Whether a screen asks is this camera's own check (confirm_refused, since 2026-11-14), made on every Enter, every press
of the multi-selector's centre and every trash button, by the screen's shape and never by what it is called
(safety.enter_refused): no Enter on a notice, a screen of no known kind, one whose text cannot be read or reads nothing,
one that shows a question mark above its footer, or a carousel that asks (safety.asks); and always on the screen on
show: it is looked at again just before the press (look_again: one fresh grab, on OSD eyes once OSD_LAG has passed
since the kit's last move) and that frame is judged (judge_fresh), so a question the camera raised by itself while the
kit read, or a popup drawn after the settle, is never answered on an older reading. The word list
(safety.confirmation_refused) judges here only a notice let through and a consent's screen; on an option screen that
passes the shape no word is judged. The ways past are explicit, named by the caller and logged: the owner route's
judgement of that very press with every check lifted (confirm_once: drive.py --owner --confirm through press's
confirm, beside drive.py's word for an owner row's step or armed press, permit); pp_reset_run's profile reset
question, ("profile_reset", "PPn"), which goes only where the screen read afresh is that question
(profile_reset_passed); a consent named for one
press on one named screen (answer_once: a prover's --allow for its own row's screen, drive.py's and card_actions.py's
--confirm "SCREEN TEXT"), which lifts the shape and never the word list, or, for a row's own dialog drawn in its portrait
arrangement held vertically (UprightDialog), judges that one Enter as a level dialog's on the frame read upright, and for
a Custom box's size editor (BoxEditor, BoxReset) or a row's two-box screen (TwoBoxes), on that screen's own shape; on a
notice, the run's --info-ok (press's
notice_ok, after proving.screens.pass_named_notice's judgement) or a refused MENU on that very screen just before
(menu_refused, leave_notice, whose OK goes on that notice alone: require_notice), each only where the notice's lit
button reads OK and is plainly its only one (safety.lone_ok). An Enter or a trash button goes to the link only with
the link's count of moving commands at that look (Link.press's judged), which the link refuses once anything has moved
since, so no press sent past this camera (proving.nav.to_shooting's, which judges with menu_refused_enter on a frame
grabbed after the refusal) escapes the check, nor a judgement grown stale.
What this check cannot see: a question drawn as an option screen with no question mark, or one whose mark OCR misses; a
list where choosing is the act (a slot in Format, an item in Delete); button words in another language on a carousel or
beside a lone OK; Right and the dials; a question the camera raises by itself just before the press (on OSD eyes,
within OSD_LAG of the kit's last move); a held Enter.

The orange cursor is found as a bar first (lit_box). A dialog or table that lights its item without one (the White
Balance chooser's orange text, a two-slot table's narrow cell) is read from the largest orange region instead, on those
screens alone: on a menu page a lit row is always a bar, and its orange texts are values on unlit rows (2026-11-08)."""
import atexit
import contextlib
import os
import re
import shutil
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import ocr, safety, screen, vlm
from .frames import keep
from .link import CameraRefused, LinkError
from .session import playback_kind
from .vlm import PROMPTS, ask_role, log_to, scrub


# Presses that open the row under the cursor, and the screens whose lit bar is a row
OPENS = frozenset({"right", "enter", "ms_right", "ms_enter"})
# Inside a row a network decision opened, the presses that may close it: MENU, and an Enter inside_refused lets through
# (an option the decision names); a network row's lock ends only after one of them (LiveCamera.network_left)
CLOSES = frozenset({"menu", "enter", "ms_enter"})
ROW_SCREENS = frozenset({"menu", "submenu"})
UNREAD = "the row under the cursor could not be read: the never-open check cannot judge it"
READER_TIMEOUT = 25.0   # s the vision reader gets to name an unread row (submenu_labels gives it as long)


# The screens whose lit item may be drawn without a bar: the White Balance chooser in Movie mode lights its item as
# orange text on black (runs/kit2_wbmovie2, 00055_down.png), the two-slot Image Quality Settings table one narrow cell
# (runs/kit2_quality2, 00028_right.png, 167 px of 640). Nowhere else: a menu or submenu page's lit row is a bar and
# its orange texts are values on unlit rows ("Standard", "1 (Fast)"), and on the shooting screen, the Main tiles or a
# screen not known what is orange need not be lit, so there nothing lit stays nothing lit (drive.py refuses)
NO_BAR_SCREENS = frozenset({"dialog", "table"})
# the closing that makes a word's letters, or a cell's fill round its text, one region; and the bounds a region keeps
# to count as one lit item: a line of text or a cell, never a speck or a block of picture
CLOSE = (15, 9)
ITEM_MIN_AREA, ITEM_HEIGHT = 300, (12, 80)


def bar_box(lit) -> tuple | None:
    """(x0, y0, x1, y1) of the orange cursor drawn as a bar (a menu row, a list's row, a dialog's button: the rows
    whose orange covers 0.3 of the width, then the columns orange in half of those rows), or None."""
    ys = (lit.mean(axis=1) > 0.3).nonzero()[0]
    if not len(ys):
        return None
    xs = (lit[ys].mean(axis=0) > 0.5).nonzero()[0]
    if not len(xs):
        return None
    return int(xs[0]), int(ys[0]), int(xs[-1]) + 1, int(ys[-1]) + 1


def item_box(lit) -> tuple | None:
    """(x0, y0, x1, y1) of a lit item drawn without a bar: the largest orange region once the mask is closed (a word's
    letters, a cell's fill, merge into one), widened to every orange region on its line, so a label whose words the
    closing left apart is lit whole; None when no region is the size of a line of text or a cell."""
    import cv2
    closed = cv2.morphologyEx(lit.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, CLOSE))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    regions = [tuple(int(v) for v in stats[i, :5]) for i in range(1, n)
               if stats[i, cv2.CC_STAT_AREA] >= ITEM_MIN_AREA and ITEM_HEIGHT[0] <= stats[i, cv2.CC_STAT_HEIGHT] <= ITEM_HEIGHT[1]]
    if not regions:
        return None
    x, y, w, h, _ = max(regions, key=lambda r: r[4])
    x0, y0, x1, y1 = x, y, x + w, y + h
    for rx, ry, rw, rh, _ in regions:
        if min(y + h, ry + rh) - max(y, ry) >= 0.5 * min(h, rh):          # on the same line
            x0, y0, x1, y1 = min(x0, rx), min(y0, ry), max(x1, rx + rw), max(y1, ry + rh)
    return x0, y0, x1, y1


def lit_found(image, kind: str | None = None) -> tuple:
    """(the orange cursor's box or None, whether it is a bar): the bar first; then, on a screen that may light its item
    without one (NO_BAR_SCREENS; kind is the screen's, read from the image when not given), the item's region
    (item_box). On a page where a bar is drawn the bar always wins, so orange value texts never stand for the lit
    item."""
    lit = screen._orange(image) > 0.5
    box = bar_box(lit)
    if box is not None:
        return box, True
    if kind is None:
        from .frames import Frame
        kind = screen.read(Frame(image=image, t=0.0)).kind
    return (item_box(lit) if kind in NO_BAR_SCREENS else None), False


def lit_box(image, kind: str | None = None) -> tuple | None:
    """(x0, y0, x1, y1) of the orange cursor (a row, a button, or a dialog's or table's lit item drawn without a bar),
    or None when nothing is lit (lit_found)."""
    return lit_found(image, kind)[0]


def line_box(box, lines) -> tuple:
    """A lit item's box (one drawn without a bar) widened to the whole of every OCR text run it touches on its line:
    a label only part of which was orange, or whose words the closing left apart, is read whole, so the never-open
    check judges all of it ("Direct Info." alone passes it, "Wi-Fi Direct Info." does not). A run elsewhere on the
    line, a table's row label or another slot's value, stays out."""
    x0, y0, x1, y1 = box
    for ln in lines:
        if box[1] <= ln.y + ln.h / 2 <= box[3] and ln.x < box[2] and ln.x + ln.w > box[0]:
            x0, x1 = min(x0, ln.x), max(x1, ln.x + ln.w)
    return x0, y0, x1, y1


def lit_text(image, path) -> str:
    """The text inside the orange cursor (a row, a button, or a dialog's or table's lit item, read whole: line_box),
    or "" when nothing is lit (or OCR reads nothing in it: lit_box tells the two apart)."""
    box, bar = lit_found(image)
    if not box:
        return ""
    lines = ocr.read([path])[path]
    return ocr.text_in(lines, box if bar else line_box(box, lines))


def reader_label(path, timeout: float = READER_TIMEOUT) -> tuple[str, str]:
    """(label, why not) of the menu row the orange bar lights on the frame at path, as the "second" vision reader
    reads it (camkit.vlm.ask_role, through which every question a run asks about a frame goes, a stand-in taking the
    role when the second will not connect; the menu question the walkers ask, PROMPTS["menu"]): the label of the one
    row it marks highlighted, or "" with the reason it gave none (no row marked, more than one, an empty label, or the
    reader failed)."""
    try:
        answer = ask_role("second", path.read_bytes(), PROMPTS["menu"], timeout)
    except Exception as e:
        return "", scrub(f"the vision reader failed ({type(e).__name__}: {e})"[:300])
    rows = answer.get("rows") if isinstance(answer, dict) else None
    lit = [r for r in rows or [] if isinstance(r, dict) and r.get("highlighted") is True]
    if len(lit) != 1:
        return "", f"the vision reader marked {len(lit)} rows as the one with the orange bar"
    label = str(lit[0].get("label") or "").strip()
    return (label, "") if label else ("", "the vision reader gave the lit row no label")


def open_refused(lit: str, may_open=frozenset(), network=frozenset(), screens: bool = False, values=None,
                 readings=None, labels=None, look: bool = False, row=None) -> str:
    """Why a press may not open the lit row, or "": the row's text is never-open, and no name the run was given
    lifts it (drive.py --allow lifts what it may; never what safety.never_lifted names: the cards, Initialize, Reset
    Network Set., credentials, and the camera's identity, a connection or its region, decision 8). A Wi-Fi or Bluetooth
    setting or an address screen (safety.NETWORK, or its words in a row of another reason) is lifted only by a dated
    owner decision naming the row (`network`, safety.network_decided's rows, for a run given --network:
    safety.network_lifted, its label, or a reading of it another reader read as the label (`readings`), followed by
    nothing or one of its `values`, an address screen only with `screens`; with no value known, a short tail that makes
    of the bar no other label of `labels`, runner.label_readings), never by the substring match of `may_open`. What is
    judged is the row (safety.row_judged): a bar that is exactly a row label the kit knows followed by exactly one of
    its known values (`values`) is judged by the label alone, so a value beside a row never refuses it.
    On a look lap (`look`: a run given --network, docs/decisions/0024) a row safety.look_lap_refused refuses never opens,
    whatever never_open says of it (look_refusal: OWNER_NEVER's rows and the Screen Reader, a row whose opening acts, a
    format, delete or reset not seen opened); any other never-open row opens only where the bar is the row its caller
    is about to open (`row`: bar_is_row) and that row is seen opened on this body or under its first open."""
    judged = safety.row_judged(lit, values, labels)
    seen, first = bar_is_row(judged, row) if look else (False, False)
    said = look_refusal(lit, judged, seen) if look else None
    if said:
        return f"the lit row {lit.strip()!r} is not opened on a look lap ({said})"
    why = next((w for w in map(safety.never_open, judged) if w), None)
    if not why:
        return ""
    if network and safety.network_lifted(lit, network, screens, values, readings, labels):
        return ""                       # a network decision names it: a Wi-Fi or Bluetooth setting, an identity row
    if look and (first or seen):
        return ""                       # a look lap opens it, to look at only (docs/decisions/0024)
    if why.startswith(safety.NETWORK + ":") and not look:
        return (f"the lit row {lit.strip()!r} is never opened ({why}; only a dated owner decision naming the row opens "
                "it, with --network)")
    # a name and the reading compared as the guards fold them: "Pre-AF" names a "Pre‑AF" read with a no-break hyphen
    read = safety.clean_label(safety.fold(lit))
    named = any(safety.clean_label(safety.fold(m)) and safety.clean_label(safety.fold(m)) in read for m in may_open)
    if named and not safety.never_lifted(lit) and not safety.network_words(lit):
        return ""
    if look:
        return (f"the lit row {lit.strip()!r} is not opened on a look lap ({why}): it is not the row the run is opening, "
                "or that row is neither seen opened on this body nor under its first open (docs/decisions/0024)")
    return f"the lit row {lit.strip()!r} is never opened ({why})"


def bar_is_row(judged, row=None) -> tuple:
    """(seen, first) for a lit bar (`judged`: safety.row_judged's texts) on a look lap: the caller's word for the row it
    is about to open (`row`: {"expected": the one name the caller asked Seen about for that row, "seen": whether
    this body's records show that row's whole path opened, "first": whether that very path's first open is under way,
    its RESTORE_BY_HAND on disk}) where every text judged is unchanged by safety.fold and, compared plain, one of
    `expected`; else (False, False): a bar that is not that row, or a press with no row named, is unseen and under no
    first open, whatever marker is on disk and whatever labels the records hold (docs/decisions/0024)."""
    if not isinstance(row, dict):
        return False, False
    told = {safety.plain(x) for x in row.get("expected") or () if isinstance(x, str) and safety.plain(x)}
    ok = bool(judged) and all(safety.fold(t).strip() == " ".join(str(t).split()) and safety.plain(t) in told
                              for t in judged)
    return (bool(row.get("seen")), bool(row.get("first"))) if ok else (False, False)


def look_refusal(lit: str, judged, seen: bool = False) -> str | None:
    """Why a look lap (a run given --network) never opens the lit row `lit`, or None (docs/decisions/0024):
    safety.look_lap_refused of the bar read whole or of the row it names (`judged`, safety.row_judged), a refusal in any
    of them winning, `seen` as bar_is_row gives it."""
    return next((w for t in dict.fromkeys((lit, *judged)) for w in [safety.look_lap_refused(t, seen)] if w), None)


def look_row(lit: str, values=None, labels=None, row=None) -> str | None:
    """The row a look lap opens the lit bar `lit` as, no decision naming it, or None: where never_open names the row
    (safety.row_judged's texts), look_refusal refuses nothing and the bar is the row its caller is opening, seen opened
    here or under its first open (bar_is_row), the bar's text as read, which the page it was opened from shows again
    once it is left (safety.bar_on_row); an ordinary row opens as ever, with no look lock."""
    judged = safety.row_judged(lit, values, labels)
    seen, first = bar_is_row(judged, row)
    if not any(safety.never_open(t) for t in judged) or look_refusal(lit, judged, seen) or not (first or seen):
        return None
    return str(lit or "").strip() or None


# what the camera's logs and messages name a row a look lap opened as, no decision naming it: a bar can carry the row's
# value, the owner's (docs/decisions/0008); the bar as read is kept in memory alone, to tell when the row is left
WITHHELD_ROW = "(withheld)"


FOOTER_TOP = 415        # px: the footer band (camkit.screen's help glyph from y 415, the footer line at 424-429) starts here
# a carousel's title line, where camkit.screen's dialog draws its lit option in orange (proving.screens.carousel_text's)
DIALOG_TITLE = (110, 60, 636, 112)
MENU_REFUSED = "the notice has just refused MENU"     # the way past a notice that refused MENU (safety.enter_refused)


@dataclass(frozen=True)
class UprightDialog:
    """A prover's consent for one Enter on its row's own dialog drawn in its portrait arrangement: held vertically with
    Vertical Display On, Focus Area's carousel is drawn so, which the SDK's picture squeezes into 640 x 480 and HDMI
    turns a quarter, and camkit.screen reads it as no known kind, whose Enter the shape check refuses (2026-11-16,
    kit2_a1fin_framepos_edges_gripdown_vdon2). Given through answer_once by afreg_run.choose_area's upright branch alone,
    after its own checks (the row's title read upright, the option it stepped to under the cursor, no confirmation's
    words), where --grip down|up is the operator's word that the camera is held so; judged here (confirm_refused:
    upright_passed) on the frame judged, read upright by `read`, as a level dialog's Enter is judged: safety.enter_refused
    as a dialog (a text read, no question mark above the footer, a carousel that asks nothing on its lit option), then
    the confirmation words, which every consent keeps; its title read upright must be the row's own. It answers no other
    kind of screen, nor the trash button, and is spent by its press. Chosen over teaching camkit.screen a portrait
    dialog kind: that kind would be trusted by every guard on every screen of its shape, from any caller, where this
    lifts one Enter on one named screen and judges it on the reading the prover already makes."""
    name: str           # the consent's words, logged with the press: "<row>'s own dialog, read upright, held vertically"
    row: str            # the row whose own dialog it is: its title read upright must be that row's (safety.clean_label)
    read: Callable      # the camera -> (title, lit option, whole text, text above the footer) of its frame read upright


@dataclass(frozen=True)
class BoxEditor:
    """A prover's consent for one Enter on a Custom focus box's own size editor, the OK that keeps the size its dials
    set: Focus Area's SET (C4) with the box lit opens it (the owner's go-ahead, 2026-11-02: kit2_freesize), and it reads
    as no known kind, whose Enter the shape check refuses, while its footer's Reset (the trash button) is a confirmation's
    word, which a named consent's word list refuses (2026-11-17). Given through answer_once by kit/provers/boxsize_run.py
    alone, under its --allow "Focus Area's SET", once it has read the screen as that box's editor; judged here
    (confirm_refused: editor_passed) on the frame judged, by the editor's own shape (box_editor_refused): its title the
    box's own, nothing above its footer but that title (the dials' icons read as a glyph or none), its footer the
    editor's three buttons (Reset, MENU Cancel, OK) and no other word, no question mark; then the confirmation words on
    what stands above the footer, which every consent keeps. It answers no other kind of screen, nor the trash button
    (the link's C4 guard refuses C4 there besides), and is spent by its press."""
    name: str           # the consent's words, logged with the press
    box: str            # the box whose editor it is ("Custom 1"): the editor's title must be that box's


@dataclass(frozen=True)
class BoxReset:
    """A prover's consent for one C4 on a Custom focus box's own size editor, its Reset, which puts that box back to
    Sony's default size and nothing else (kit2_freesize 00563 -> 00564, the editor left open on the default box): the
    a1 II's owner's word of 2026-11-17 (decision 7). Given through answer_once by kit/provers/boxsize_run.py alone,
    under its --allow "Custom box Reset", only where the box's start size is its default records' (so a Reset restores
    exactly what the run found), once it has read the screen as that box's editor; judged here (confirm_refused:
    reset_passed) on the frame judged, by the editor's own shape as BoxEditor's OK is (box_editor_refused) and by the
    confirmation words above its footer; then, for that one C4 alone, the link is handed decision 7's size editor kind
    (safety.C4_BOX_EDITOR), which its C4 guard names, where it would be handed this screen's own (no known kind, which
    it refuses). It answers no other key nor any other kind of screen, and is spent by its press."""
    name: str           # the consent's words, logged with the press
    box: str            # the box whose editor it is ("Custom 1"): the editor's title must be that box's


@dataclass(frozen=True)
class TwoBoxes:
    """A prover's consent for one Enter on its row's own two-box screen, the OK that leaves it: S&Q and Time-lapse Frame
    Rate Settings (Movie mode) read as no known kind, whose Enter the shape check refuses (kit2_pass2 240079, XAVC HS
    4K, 2026-11-17; the proofs before 2026-11-14 pressed it unguarded). The value a box shows is already the setting:
    stepped to 24p and left with MENU, the box's row read "Recording Frame Rate: 24p" (240080) and the download after
    held it (240083), so the OK only leaves. Given through answer_once by kit/provers/boxes_run.py alone, once it has
    stepped its box to the value it proves; judged here (confirm_refused: boxes_passed) on the frame judged, by the
    screen's own shape (two_boxes_refused): its title ends with the row's name, each box's name stands above that box,
    each box reads a value, no question mark above the footer, no line where the screen draws none (the lines under the
    boxes are its own explanation), the footer drawing its Help button and its OK key and nothing else, OCR reading no
    word in it but OK (the OK judged as drawn, 2026-11-18); then the confirmation words on what stands above
    the footer, which every consent keeps. It answers no other kind of screen, nor the trash button, and is spent by its
    press. Chosen over teaching camkit.screen a two-box kind: that kind would be trusted by every guard on every screen
    of its shape, from any caller, where this lifts one Enter on one named row's screen."""
    name: str           # the consent's words, logged with the press
    row: str            # the row whose screen it is: the breadcrumb must end with that row's name
    boxes: tuple        # the two boxes' names, left first, as the screen draws them above the boxes
    at: tuple           # the two boxes' places (x0, y0, x1, y1), as the prover measured them (boxes_run.LAYOUTS)


@dataclass(frozen=True)
class OptionBoxes:
    """A prover's consent for one Enter on a list row's option that draws a row of boxes of its own, the OK that keeps
    the value its lit box was stepped to: the a1 II's Zebra Level > Custom 1 and Custom 2 (Type, Standard, Range, Lower
    Limit; 2026-11-18). With Touch Operation Off the screen reads as a dialog, whose Enter the shape check judges as
    any; read as no known kind (the same screen through other eyes, or with the touch buttons drawn), it is judged here
    (confirm_refused: option_passed) by its own shape (option_boxes_refused): the title line names the option, the word
    above the lit box is the box's, that box is lit and holds the value, the footer draws the OK key, and no question
    mark or confirmation's word stands above the footer. Given through answer_once by kit/provers/optboxes_run.py alone,
    which makes the same check before every OK; it answers no other kind of screen, nor the trash button, and is spent
    by its press."""
    name: str           # the consent's words, logged with the press
    option: str         # the list's option whose boxes these are ("Custom 1"): its title line must name it
    word: str           # the word the camera writes above the lit box ("Standard")
    value: str          # the value that box must hold ("71", "±6", "Lower Limit")
    at: tuple           # where that box stands (x0, y0, x1, y1), as the prover measured it (optboxes_run.PLACES)
    places: tuple = ()  # every place of the row (optboxes_run.PLACES): where given, `at` must be the one lit of them


@dataclass(frozen=True)
class PanelSlider:
    """A prover's consent for one Enter on a panel's slider, the OK that keeps the number Left and Right stepped it to:
    the a1 II's Monitor Brightness and Viewfinder Bright. (a setup row, Brightness Setup, its option at the right; under
    it the slider, lit by an orange frame; a test chart below) read as no known kind, whose Enter the shape check refuses
    (kit2_pass2 252551, 2026-11-19; the proofs of 2026-11-10 pressed it unguarded, before 2026-11-14). Given through
    answer_once by kit/provers/scale_run.py alone, for a --panel-row, once it has read the slider on the number it
    proves; judged here (confirm_refused: panel_passed) by the panel's own shape (panel_slider_refused): its title the
    row's, the slider lit (an orange line across it at its top and at its bottom: drawn only with the setup row on the
    option that shows it) and the setup row not, no question mark above the footer, no line where the panel draws
    none, the footer drawing its Help button, its MENU key and its OK key and nothing else, OCR reading no word in it but
    MENU and OK; then the confirmation words on what stands above the footer, which every consent keeps. It answers no
    other kind of screen, nor the trash button, and is spent by its press."""
    name: str           # the consent's words, logged with the press
    row: str            # the panel's row ("Monitor Brightness"): its title must start with that name
    slider: tuple       # where the slider's frame is drawn (x0, y0, x1, y1), as the prover measured it (scale_run)
    setup_at: tuple     # where the setup row's option stands (x0, y0, x1, y1): the row is that band, the whole width


# the option's title line (its lit option under the row's name, "Custom 1") and the band where the camera writes the lit
# box's name above the row of boxes (kit2_look_zebra_a 00013-00015, kit2_zebra_split: "Type", "Standard", "Range")
OPTION_TITLE = (110, 60, 400, 106)
BOX_WORD = (100, 280, 640, 342)
VALUE_FOLD = str.maketrans({"‡": "±"})      # OCR's reading of the ± before a range ("‡5")
# OCR's readings of the sign before a range's digits: all of them the box's own ± (kit2_pass2 241418-241440, the probe's
# Range walk: "+5", "÷4", "¢5", "‡1", "±6"), and of the digits' look-alikes in a box of digits alone (241426 and 241431
# read a 3 as Cyrillic З; O, О, l, I and | are no digit's reading but these in such a field)
BOX_SIGNS = "±+÷¢‡"
DIGIT_FOLD = str.maketrans({"З": "3", "з": "3", "О": "0", "о": "0", "O": "0", "o": "0", "l": "1", "I": "1", "|": "1"})
_NUMBER_SHAPE = re.compile(rf"([{re.escape(BOX_SIGNS)}]?)([0-9ЗзОоOolI|]+)(\+?)")


def box_shape(like) -> tuple | None:
    """(sign, suffix) of a box's values shaped as `like`, one of them: a sign before the digits (whatever glyph OCR read
    for it, the box's own ±) and a "+" after them (a lower limit's "100+"), each "" where there is none; None for a value
    of words (Type's "Std+Range")."""
    m = _NUMBER_SHAPE.fullmatch(re.sub(r"\s+", "", str(like or "")))
    return ("±" if m.group(1) else "", m.group(3)) if m else None


def box_value(text, like) -> str:
    """`text`, read in a box whose values are shaped as `like`, put in that shape: the sign the box's own (±) whatever
    glyph OCR read for it, the digits mapped from their look-alikes (DIGIT_FOLD), a trailing "+" kept where the box has
    one; spaces out. Where `like` is no number's shape (a box of words) or `text` holds no clean digits, `text` as read,
    its spaces out, for the caller to judge."""
    t = re.sub(r"\s+", "", str(text or ""))
    shape = box_shape(like)
    if shape is None:
        return t
    sign, suffix = shape
    core = t.lstrip(BOX_SIGNS) if sign else t
    core = core.rstrip(BOX_SIGNS) if suffix else core
    digits = core.translate(DIGIT_FOLD)
    return f"{sign}{digits}{suffix}" if re.fullmatch(r"\d+", digits) else t


def box_number(text, like) -> int | None:
    """The number `text` reads in a box shaped as `like` (box_value), or None where it reads no clean one."""
    if box_shape(like) is None:
        return None
    m = re.fullmatch(r"±?(\d+)\+?", box_value(text, like))
    return int(m.group(1)) if m else None


def boxes_drawn(image, places) -> int:
    """How many boxes of the row `places` the screen draws, by their outlines: the places, from the first on, whose top
    edge is drawn (grey, about 90 on a drawn box, 0 where none is: kit2_pass2 241720 draws two under Lower Limit, 241717
    three under Std+Range), or lit."""
    g = np.asarray(image, np.float32)
    g = g[..., :3].mean(axis=2) if g.ndim == 3 else g
    lit = set(boxes_lit(image, places))
    n = 0
    for i, (x0, y0, x1, y1) in enumerate(places):
        edge = float(g[y0:y0 + 3, x0 + 8:x1 - 8].max(axis=0).mean()) if y1 > y0 + 3 and x1 > x0 + 16 else 0.0
        if edge <= 40 and i not in lit:
            break
        n += 1
    return n


def boxes_lit(image, places) -> list:
    """The places of the row that are filled orange (camkit.screen._orange over 0.3; a lit box is 0.66-0.84, an unlit
    one 0.0 on the a1 II's frames), in order. Pixels alone: no reader is asked whether a box is lit."""
    o = screen._orange(np.asarray(image))
    return [i for i, (x0, y0, x1, y1) in enumerate(places) if o[y0:y1, x0:x1].size and float(o[y0:y1, x0:x1].mean()) > 0.3]


def in_box_refused(option: str, word: str | None, at: int, places, lines, image) -> str:
    """Why the screen is not `option`'s row of boxes with its box `at` (of `places`) the one lit and named `word` above
    the row, or "" when it is: the title line names the option, exactly one box of the row is filled orange, by pixels
    (boxes_lit), and it is `at`, and the word above the row is `word` (where None, a box not yet named, whatever it
    reads: its name is then read, by the second reader where OCR's reading is empty or not plain Latin,
    kit/provers/optboxes_run.py's box_name).
    kit/provers/optboxes_run.py's check after every press inside the boxes and before every reading there: a Right on
    the last box leaves the boxes for the list, whose cursor then moves with Up and Down (kit2_pass2 241721, 241724,
    241752-241754), which the prover must never take for a box."""
    title = ocr.text_in(lines, OPTION_TITLE).strip()
    if not _compact(title) or _compact(title) != _compact(option):
        return f"its title line reads {title[:40]!r}, not {option}"
    lit = boxes_lit(image, places)
    if not lit:
        return "no box of the row is lit (the list's cursor, or no row of boxes, is on show)"
    if lit != [at]:
        return f"box {lit[0] + 1} of the row is lit, not box {at + 1}" if len(lit) == 1 else f"{len(lit)} boxes are lit"
    said = ocr.text_in(lines, BOX_WORD).strip()
    if word is None:
        return ""
    return "" if _compact(said) == _compact(word) else f"the word above the row reads {said[:40]!r}, not {word}"


def option_boxes_refused(consent: OptionBoxes, lines, image, read: str | None = None) -> str:
    """Why a screen whose OCR lines are `lines` and whose picture is `image` is not `consent.option`'s row of boxes with
    its `consent.word` box lit on `consent.value`, ready for the OK that keeps it (OptionBoxes), or "" when it is: the
    title line names the option and the word above the lit box is the box's (both compared without spaces or
    punctuation), the box at `consent.at` is lit (orange) and reads the value (OCR's reading in the value's shape,
    box_value; `read`, the caller's own reading of it, its second reader's among them, where given), the footer draws
    the OK key (camkit.screen.footer_keys), no question mark and no confirmation's word above the footer. The first
    three are the prover's check after every press (in_box_refused), on every place of the row where the consent names
    them (`places`: the box at `at` the one lit of them), else on `at` alone."""
    places = tuple(consent.places) or (tuple(consent.at),)
    why = in_box_refused(consent.option, consent.word, places.index(tuple(consent.at)), places, lines, image)
    if why:
        return why
    value = box_value(read if read is not None else ocr.text_in(lines, consent.at), consent.value)
    if value != box_value(consent.value, consent.value):
        return f"the {consent.word} box reads {value!r}, not {consent.value!r}"
    if "ok_key" not in screen.footer_keys(image):
        return "its footer draws no OK key"
    body = ocr.text_in(lines, (0, 0, 640, FOOTER_TOP))
    if safety.question_mark(body):
        return "it holds a question mark above its footer"
    words = safety.confirmation_refused(body)
    return f"it reads as a confirmation ({words})" if words else ""


# a two-box screen's breadcrumb; where a box's name stands, measured from the box (kit2_pass2 240079: "Rec Frame Rate"
# 65-93 px down above the box at 178, the name a little wider than the box at either side)
BOXES_TITLE = (0, 0, 640, 40)
NAME_ABOVE = (20, 125, 70)          # px: beyond the box's sides; from its top up to the name's band, its top and bottom


def boxes_lines(cam) -> list:
    """The OCR lines of a row's two-box screen on the frame judged (TwoBoxes)."""
    f = cam.frame
    return ocr.read([f.path])[f.path]


def _compact(t) -> str:
    return re.sub(r"[^a-z0-9]", "", safety.fold(str(t or "")).lower())


def _above(box) -> tuple:
    """Where a two-box screen draws a box's name (NAME_ABOVE): over the box, a little wider than it."""
    side, up, down = NAME_ABOVE
    x0, y0, x1, _ = box
    return (x0 - side, y0 - up, x1 + side, y0 - down)


def names_drawn(lines, at, names) -> list | None:
    """The two box names `names` (in any order) in the order a two-box screen whose OCR lines are `lines` draws them
    over its boxes `at`, left first: each box's text above it (where TwoBoxes reads it) ending with one of them, the
    longest that fits ("Sad Rec Frame Rate" ends with Frame Rate too: it is Rec Frame Rate's); None where the two boxes
    do not give the two names once each (another row's screen, a name OCR misread)."""
    out = []
    for box in at:
        said = _compact(ocr.text_in(lines, _above(box)))
        fits = [n for n in names if _compact(n) and said.endswith(_compact(n))]
        out.append(max(fits, key=lambda n: len(_compact(n))) if fits else None)
    return out if None not in out and sorted(out) == sorted(names) and len(set(out)) == len(names) else None


def two_boxes_refused(consent: TwoBoxes, lines, image) -> str:
    """Why a screen whose OCR lines are `lines` and whose picture is `image` is not `consent.row`'s own two-box screen,
    shaped as it is (TwoBoxes), or "" when it is: its breadcrumb ends with the row's name and each box's name stands
    above that box (compared without spaces or punctuation, so an icon OCR reads as letters before it, "Sad Rec Frame
    Rate", or glued on, stays the name); each box reads a letter or a digit; no question mark above the footer; every
    line above the footer stands on the breadcrumb, a box's name, a box, or under the boxes (the screen's own lines: "x5
    Slow Motion", "Shooting time required for 5-second movie recording."), a lone glyph (an arrow) anywhere. Its footer:
    OCR reads no word in it but OK (its trash icon and help glyph read as nothing, a letter, or "?"), and as drawn
    (camkit.screen.footer_keys, the kit's own glyphs, found by pixels) it holds the Help button (trash and "?") and the
    OK key ("● OK") and no ink besides them (footer_ink_outside: a second button, whatever OCR read of it). The OK is
    judged as drawn, never by OCR finding it: on kit2_pass2 240268 (2026-11-18) OCR read that footer's "?" alone, the
    OK drawn pixel for pixel as on the frames it read "• OK". Fail closed: a screen read or drawn otherwise stops the
    run before its OK."""
    def text_at(box):
        return ocr.text_in(lines, box).strip()
    title = text_at(BOXES_TITLE)
    if not _compact(consent.row) or not _compact(title).endswith(_compact(consent.row)):
        return f"its title ({title[:60]!r}) does not end with {consent.row}"
    places = [BOXES_TITLE]
    for name, (x0, y0, x1, y1) in zip(consent.boxes, consent.at, strict=True):
        above = _above((x0, y0, x1, y1))
        said = text_at(above)
        if not _compact(name) or not _compact(said).endswith(_compact(name)):
            return f"the name above a box ({said[:40]!r}) is not {name}"
        if not re.search(r"[^\W_]", text_at((x0, y0, x1, y1))):
            return f"its box {name} reads no value"
        places += [above, (x0, y0, x1, y1)]
    places.append((0, max(b[3] for b in consent.at), 640, FOOTER_TOP))
    if safety.question_mark(text_at((0, 0, 640, FOOTER_TOP))):
        return "it holds a question mark above its footer"
    for ln in lines:
        if ln.y + ln.h / 2 < FOOTER_TOP and not any(ln.inside(p) for p in places) \
                and len(re.findall(r"[^\W\d_]", ln.text)) > 1:
            return f"a line ({ln.text.strip()[:40]!r}) stands where its screen draws none"
    words = re.findall(r"[a-z]{2,}", safety.fold(text_at((0, FOOTER_TOP, 640, 480))).lower())
    others = [w for w in words if w != "ok"]
    if others:
        return f"its footer reads {others[0]!r}, not its OK alone"
    keys = screen.footer_keys(image) if image is not None else {}
    if "ok_key" not in keys:
        return "its footer offers no OK (no OK key drawn in it)"
    if "help_only" not in keys:
        return "its footer lacks its Help button (trash and ?)"
    stray = screen.footer_ink_outside(image, [keys["ok_key"], keys["help_only"]])
    return f"its footer draws more than its Help button and OK (ink at {stray})" if stray else ""


PANEL_TITLE = (0, 0, 640, 60)
PANEL_EDGE = 8          # px: rows at the slider's top and bottom edge where its lit frame's orange line is looked for
PANEL_KEYS = ("menu", "ok")             # the only words OCR may read in a panel's footer (its MENU key, its OK)


def menu_back_key(image) -> tuple | None:
    """Where the footer draws its MENU key with the back arrow (glyphs/menu_back.png, cut from the a1 II's panel footer,
    kit2_pass2 252551), found by its template as camkit.screen.footer_keys finds its keys: (x0, y0, x1, y1), or None
    where its best match scores 0.9 or less (the panels' 0.97 to 1.0; MENU Close or MENU Cancel score under 0.7)."""
    import cv2
    g = np.asarray(image, np.float32)
    if g.ndim == 3:
        g = g[..., :3] @ np.array([0.299, 0.587, 0.114], np.float32)
    t = screen._template("menu_back")
    _, best, _, (x, y) = cv2.minMaxLoc(cv2.matchTemplate(g[FOOTER_TOP:480, :], t, cv2.TM_CCOEFF_NORMED))
    return (x, FOOTER_TOP + y, x + t.shape[1], FOOTER_TOP + y + t.shape[0]) if best > 0.9 else None


def slider_lit(image, at, setup_row) -> bool:
    """Whether a panel's slider is lit on `image`: an orange line runs across the slider's whole width (`at`) in the rows
    at its top edge and in those at its bottom edge (PANEL_EDGE: Monitor Brightness's lines over HDMI at y 138 and 265,
    Viewfinder Bright.'s frame over the OSD picture down to 269), and the setup row (`setup_row`) is not lit (an orange
    bar over it: under a fifth of it orange, its option's orange letters aside). By pixels alone."""
    o = screen._orange(image)
    x0, y0, x1, y1 = at

    def line(rows) -> bool:
        return bool(rows.size) and bool((rows.mean(axis=1) >= 0.9).any())
    r0, r1 = setup_row[1], setup_row[3]
    return line(o[y0:y0 + PANEL_EDGE, x0:x1]) and line(o[y1 - PANEL_EDGE:y1, x0:x1]) and float(o[r0:r1].mean()) < 0.2


def panel_slider_refused(consent: PanelSlider, lines, image) -> str:
    """Why a screen whose OCR lines are `lines` and whose picture is `image` is not `consent.row`'s panel with its slider
    lit, shaped as it is (PanelSlider), or "" when it is: its title starts with the row's name ("Viewfinder Bright"
    for Viewfinder Bright.); its slider lit and its setup row not (slider_lit, by pixels: the slider is drawn only on the
    setup option that shows it, so its words are not read, which OCR spells "Manua" on some frames); no question mark
    above the footer; every line above the footer stands on the title, the setup row, the slider or the test chart
    under it, a lone glyph anywhere. Its footer: OCR reads no word in it but MENU and OK (a glyph glued before one read
    as a letter: "iMENU", "cOK" over the OSD picture), and as drawn it holds the Help button, the MENU key
    (menu_back_key) and the OK key (camkit.screen.footer_keys) and no ink besides them (footer_ink_outside). The OK
    judged as drawn, never by OCR finding it. Fail closed: a screen read or drawn otherwise stops the run before its
    OK."""
    def text_at(box):
        return ocr.text_in(lines, box).strip()
    title = text_at(PANEL_TITLE)
    if not _compact(consent.row) or not _compact(title).startswith(_compact(consent.row)):
        return f"its title ({title[:60]!r}) is not {consent.row}'s"
    setup_row = (0, consent.setup_at[1], 640, consent.setup_at[3])
    if image is None or not slider_lit(image, consent.slider, setup_row):
        return "its slider is not lit (no orange line across its top and its bottom, or its setup row lit)"
    if safety.question_mark(text_at((0, 0, 640, FOOTER_TOP))):
        return "it holds a question mark above its footer"
    x0, _, x1, y1 = consent.slider
    places = [PANEL_TITLE, setup_row, consent.slider, (x0, y1, x1, FOOTER_TOP)]
    for ln in lines:
        if ln.y + ln.h / 2 < FOOTER_TOP and not any(ln.inside(p) for p in places) \
                and len(re.findall(r"[^\W\d_]", ln.text)) > 1:
            return f"a line ({ln.text.strip()[:40]!r}) stands where its panel draws none"
    words = re.findall(r"[a-z]{2,}", safety.fold(text_at((0, FOOTER_TOP, 640, 480))).lower())
    others = [w for w in words if not any(w == k or (len(w) == len(k) + 1 and w.endswith(k)) for k in PANEL_KEYS)]
    if others:
        return f"its footer reads {others[0]!r}, not its MENU and OK alone"
    keys = screen.footer_keys(image)
    if "ok_key" not in keys:
        return "its footer offers no OK (no OK key drawn in it)"
    menu = menu_back_key(image)
    if "help_only" not in keys or menu is None:
        return "its footer lacks its Help button (trash and ?) or its MENU key"
    stray = screen.footer_ink_outside(image, [keys["ok_key"], keys["help_only"], menu])
    return f"its footer draws more than its Help button, MENU and OK (ink at {stray})" if stray else ""


# the size editor's title, top left above the box (kit2_freesize's 00394_c4.png); its footer's words, a key's word cut
# short or an icon's glyph run onto it aside (box_editor_refused)
EDITOR_TITLE = (0, 0, 400, 60)
EDITOR_KEYS = ("reset", "menu", "cancel", "ok")


def editor_texts(cam) -> tuple:
    """(title, text above the footer band, footer) of a Custom box's size editor on the frame judged (BoxEditor)."""
    f = cam.frame
    lines = ocr.read([f.path])[f.path]
    return (ocr.text_in(lines, EDITOR_TITLE).strip(), ocr.text_in(lines, (0, 0, 640, FOOTER_TOP)).strip(),
            ocr.text_in(lines, (0, FOOTER_TOP, 640, 480)).strip())


def box_editor_refused(box: str, title, body, footer) -> str:
    """Why a screen read as `title`, `body` (above the footer band) and `footer` is not `box`'s own size editor, shaped
    as the editor is (BoxEditor), or "" when it is: its title the box's (safety.clean_label, an icon's glyph before it
    left out); no question mark; above the footer nothing but the title, the dials' icons read as a single letter or
    none; in the footer Reset, Cancel and OK, and no word besides MENU or a piece of it ("MEN": the key's glyph cut
    short) or one glyph run onto a button's word ("iReset": the trash icon). Fail closed: an editor OCR reads otherwise
    stops the walk before its OK."""
    if not safety.clean_label(title) or safety.clean_label(title) != safety.clean_label(box):
        return f"its title ({str(title or '').strip()[:40]!r}) is not {box}'s"
    if safety.question_mark(f"{body} {footer}"):
        return "it holds a question mark"
    rest = safety.fold(str(body or "")).lower().replace(safety.clean_label(box), " ", 1)
    extra = re.findall(r"[a-z]{2,}", rest)
    if extra:
        return f"above its footer it shows more than its title ({extra[0]!r})"
    words = []
    for w in re.findall(r"[a-z]+", safety.fold(str(footer or "")).lower()):
        words.append(w if w in EDITOR_KEYS or w[1:] not in EDITOR_KEYS else w[1:])
    others = [w for w in words if w not in EDITOR_KEYS and len(w) > 1 and w not in "menu"]
    if others:
        return f"its footer reads {others[0]!r}, none of the editor's buttons"
    missing = [w for w in ("reset", "cancel", "ok") if w not in words]
    return f"its footer lacks the editor's {missing[0]!r}" if missing else ""


def body_of(cam) -> str:
    """The text OCR reads above the footer band (FOOTER_TOP): a screen's message, options and buttons, without its
    footer's key hints and help glyph, whose "?" no question mark check takes for one (safety.enter_refused)."""
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], (0, 0, 640, FOOTER_TOP)).strip()


def title_of(cam) -> str:
    """A carousel's title line as OCR reads it (DIALOG_TITLE): its lit option, read there where the orange region
    lit_text finds is the selected icon (a title of one or two characters)."""
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], DIALOG_TITLE).strip()


def notice_read(image, path) -> tuple:
    """(OCR lines, the orange cursor's box or None, the text inside it) of the screen at `path`, its picture `image`: what
    safety.lone_ok judges a notice by. Raises when the frame or its text cannot be read."""
    box, _ = lit_found(image, "notice")
    lines = ocr.read([path])[path]
    return lines, box, (ocr.text_in(lines, box) if box else "")


def lone_of(image, path) -> str:
    """safety.lone_ok on the notice at `path` (its picture `image`): why its lit button is not plainly its only one, or
    "" (notice_read); a notice that cannot be read is no lone OK."""
    try:
        lines, box, lit = notice_read(image, path)
    except Exception as e:
        return f"it cannot be read ({type(e).__name__})"
    return safety.lone_ok(lit, [(ln.text, ln.x, ln.y, ln.w, ln.h) for ln in lines], box)


def menu_refused_enter(kind, image, path) -> str:
    """Why OK may not go on the screen at `path` (its picture `image`, read as `kind`) right after the camera refused MENU
    on it, or "": safety.enter_refused with that way past (MENU_REFUSED) and the notice's lone OK (safety.lone_ok). The
    judgement proving.nav.to_shooting makes before the OK it sends straight through the link (Link.press's `judged`),
    with no LiveCamera to read the screen: the same check LiveCamera.confirm_refused makes after a refused MENU. Only a
    notice: a refused MENU vouches for nothing else (an option screen's Enter would open or choose)."""
    if kind != "notice":
        return f"the screen reads as {kind!r}, not a notice: a refused MENU vouches for an OK on a notice alone"
    try:
        lines, box, lit = notice_read(image, path)
    except Exception as e:
        return f"the {kind} screen cannot be read ({type(e).__name__}), so whether it asks cannot be told"
    lone = safety.lone_ok(lit, [(ln.text, ln.x, ln.y, ln.w, ln.h) for ln in lines], box)
    return safety.enter_refused(kind, ocr.text_in(lines, (0, 0, 640, 480)), lit,
                                ocr.text_in(lines, (0, 0, 640, FOOTER_TOP)), MENU_REFUSED, lone)


# what an owner decision's permit allows that lifts the camera's check of what the screen asks (drive.py's word for an
# owner row's step or armed press: LiveCamera.confirm_refused)
ARMED_WHATS = ("step", "confirm", "final", "choose")
# s the camera's own picture (OSD eyes) can lag the screen: it froze 3.25 s while the camera went on (2026-11-06,
# camkit.frames.OsdSource), and OK held it about 3 s. A freeze longer than this (6.6 s was seen once) is not covered.
# On the a1 II's OSD runs the next Enter was sent a median 1.17 s after the move before it (90 runs, 17,100 Enters), so
# the wait before its look (osd_wait) is a median 2.3 s
OSD_LAG = 3.5


def osd_wait(moved_at, now: float | None = None) -> float:
    """How long an OSD frame grabbed now could still be older than the kit's own last move (camkit.link.Link.moved_at,
    None before any): OSD_LAG after that move, less the time gone since; 0 when it has passed."""
    if moved_at is None:
        return 0.0
    return max(0.0, moved_at + OSD_LAG - (time.monotonic() if now is None else now))


def look_again(eyes, judged, tag: str, moved_at=None, read=None) -> tuple:
    """(why the screen on show now is not the screen judged, or "", the frame grabbed, None when none could be): the
    screen `judged` (a camkit.screen.Screen) compared with one fresh grab of `eyes`, read again (same_screen:
    screen.same_state), so a question the camera raised by itself while the kit read, or a popup drawn after the
    settle's quiet window, is seen before an Enter answers it. On the camera's own picture (OSD eyes, which can lag the
    screen by seconds) the grab waits until OSD_LAG has passed since the kit's own last move (`moved_at`: osd_wait), so
    the frame shows that move's outcome (2026-11-14, a review: it replaced a second grab OSD_LAG after the first, which
    caught the same and cost 3.5 s on every Enter; a question the camera raises by itself within OSD_LAG of the press is
    missed by both). Nothing is pressed or saved. A grab or a reading that fails is a refusal. "Same state" compares the
    screen's kind and structure (a list: its title strip and lit row), not every word: the caller judges the frame
    returned (LiveCamera.confirm_refused reads its text afresh). read: how the fresh frame is read (camkit.screen.read
    by default; a LiveCamera's own reading, LiveCamera.lit_by_reader)."""
    if getattr(eyes, "name", "") == "osd":
        wait = osd_wait(moved_at)
        if wait > 0:
            time.sleep(wait)
    try:
        f = eyes.grab(f"{tag}-again", save=False)
        now = (read or screen.read)(f)
    except Exception as e:
        return f"the screen could not be looked at again before the press ({type(e).__name__})", None
    if not same_screen(now, judged):
        return (f"the screen changed since it was judged (now {getattr(now, 'kind', None)!r}): the press is not sent "
                "on a screen nobody judged"), f
    return "", f


def same_picture(a, b) -> bool:
    """Whether two frames hold the very same picture, pixel for pixel (LiveCamera.look_before keeps the caller's frame
    then, whose text is read already); a frame without a picture is no such proof."""
    x, y = getattr(a, "image", None), getattr(b, "image", None)
    return isinstance(x, np.ndarray) and isinstance(y, np.ndarray) and x.shape == y.shape and np.array_equal(x, y)


def same_box(a, b, tol: int = 4) -> bool:
    """Whether two lit boxes (lit_box) mark one place, each edge within `tol` pixels (a row is about 30 tall); no box
    is no proof."""
    return a is not None and b is not None and len(a) == len(b) and all(abs(x - y) <= tol for x, y in zip(a, b, strict=True))


def same_screen(a, b) -> bool:
    """Whether two readings are of one screen (screen.same_state; the very reading, too); a reading that cannot be
    compared is no proof that it is."""
    if a is b and a is not None:
        return True
    try:
        return screen.same_state(a, b)
    except Exception:
        return False


def info_ok_text(cam) -> str:
    """The notice on show's text as --info-ok would name it: OCR's reading, its OK (a line that is a button's word alone)
    and its "Don't show this again." line left out; "" where it cannot be read."""
    try:
        lines = ocr.read([cam.frame.path])[cam.frame.path]
    except Exception:
        return ""
    kept = [ln.text for ln in lines if not safety.DONT_SHOW.search(safety.fold(ln.text or ""))
            and not any(safety._BUTTON_LINE.fullmatch(r) for r in safety.readings(ln.text))]
    return " ".join(" ".join(kept).split())


def info_ok_hint(cam, row: str, frame: str, said: str, words: bool = True) -> str:
    """How a refusal on a notice not passed ends: the --info-ok that names it for `row`, to be checked against its frame
    `frame` (`said`: info_ok_text, read on that frame). The refusal is logged in the run's events.jsonl
    ("notice_not_passed": the row, the frame and the text; on a --network or --owner run only what safety.notice_kept
    keeps of it). With `words` False (a run whose notices may name another setting's value, decision 16: afreg_run's and
    framepos_run's setup, a --network run) the text is in no message: it names the frame and the row and says where
    the text is, so the owner can still build the flag (proving.screens.pass_note, kit/drive.py, the crawl)."""
    run = getattr(cam, "run", None)
    if run is not None:
        private = getattr(cam, "network", None) or getattr(cam, "owner", None) or getattr(cam, "look", False)
        run.log("notice_not_passed", row=row, frame=frame, notice=safety.notice_kept(said) if private else said)
    if words:
        return f'check its text against {frame} and add --info-ok "{row or "ROW"}={said or "<its whole text>"}"'
    return (f'its text is in the run\'s events.jsonl ("notice_not_passed", frame {frame}): check it against {frame} and '
            f'add --info-ok "{row or "ROW"}=<that text>"')


def leave_notice(cam) -> str:
    """Out of a notice the kit does not answer: MENU first, which confirms nothing (on the a1 II it closes an information
    notice and the menu with it, and cancels a question). Only where the camera refuses MENU there ("button not
    accepted": camkit.link.CameraRefused, which LiveCamera.press records) does Enter go, and the camera's own check
    lets it go only when the notice shows no question mark and its lit button is plainly its only one
    (safety.enter_refused, safety.lone_ok): "the one case of a notice that has just refused MENU where OK is its only
    button" (2026-11-14), how the a1 II's "not available as follows" notices are left. The OK is bound to that very
    notice (LiveCamera.press's require_notice): a screen read afresh as anything else gets no Enter. Only the camera's
    own refusal counts: a MENU that failed otherwise (no reply, a button left held) raises, and no OK goes. Returns
    "menu" when MENU was taken, "ok" when OK went; a refusal of that OK raises (safety.Refused)."""
    try:
        cam.press("menu")
        return "menu"
    except CameraRefused:
        pass
    cam.press("enter", require_notice=True)
    return "ok"


OK_LATE = 4.0           # how long OK gets to show when the camera is busy applying what it chose (seconds)
# a frame older than this is looked at afresh before a press or a dial is judged on it and measured from it
# (LiveCamera._recent). HDMI gives a frame every 16.7 ms (59.94 fps) and a press takes about 65 ms; a press's settle ends
# on a fresh grab, and the caller's own reading before the next press (OCR, about 0.1-0.3 s a frame) leaves it younger
# than this, so the normal path takes no extra grab. The camera changes with nothing sent on its own time: a menu drawn
# 0.2-0.46 s after MENU (kit2_speed_lock_mv), the saving notice gone about 2 s after a download's reply; any sleep,
# lock wait or reader's call between a read and a press (0.5 s and more) gets its fresh look
STALE_S = 0.5
MENU_LATE = 1.5        # s a MENU from the shooting screen is given before a fresh frame may say it was not taken
MENU_PAGES = ("menu", "submenu", "tiles")
MENU_POLL = 0.05       # s between two looks while a MENU from the shooting screen is watched (menu_watch, menu_check)
# times a press is judged again from the top after the reader named its lit row on a frame by then stale (lit_by_reader)
REJUDGES = 2
# a frame this dark on average may show no screen to read: HDMI blanked (camkit.session.osd_shooting's level)
BLACK = 6.0
# what the camera draws to be read, its text, glyphs and box lines, is at least this grey (white text 200-250 over HDMI,
# 221 over its own picture) or orange; a blanked frame and its noise reach it in no 2 x 2 block of pixels. A frame with
# at least INK_MIN such blocks shows something to read whatever the scene behind it: the a1 II's "Added." alone, the
# smallest notice the runs hold, has 400 (kit2_pass2 223037, mean 1.0); "Lens: Invalid with this lens." over a capped
# lens 3,128 (kit2_fin_look_zring1 00028, mean 4.1, taken for black on 2026-11-19)
INK = 128
INK_MIN = 100


def dark(frame) -> bool:
    """The frame's picture is this dark on average (BLACK), whatever is drawn on it; a frame without a picture is not.
    LiveCamera.judged_screen asks the camera's own picture about a screen of no known kind on such a frame."""
    image = getattr(frame, "image", None)
    return isinstance(image, np.ndarray) and image.size > 0 and float(image.mean()) <= BLACK


def drawn(image) -> bool:
    """Whether the camera drew something to read on the picture `image`: at least INK_MIN 2 x 2 blocks of pixels each at
    INK grey or brighter, or orange (camkit.screen's planes). Noise, a pixel here and there, makes no such block."""
    a = np.asarray(image)
    lit = (screen._grey(a) >= INK) | screen._orange(a) if a.ndim == 3 and a.shape[2] >= 3 else a.reshape(a.shape[:2]) >= INK
    solid = lit[:-1, :-1] & lit[1:, :-1] & lit[:-1, 1:] & lit[1:, 1:]
    return int(solid.sum()) >= INK_MIN


def black(frame) -> bool:
    """The frame shows nothing to read: its picture this dark on average (dark) with nothing drawn on it (drawn), as
    HDMI blanked shows (Auto Framing in Movie mode). A notice or a shooting screen over a dark scene is not black: its
    text is drawn (2026-11-19, a capped lens's notice taken for black ended a first open with RESTORE_BY_HAND). A frame
    without a picture is not."""
    return dark(frame) and not drawn(frame.image)


def osd_kind(link, folder=None) -> str:
    """The kind of screen the camera's own picture of it reads as (the SDK's OSD image, fetched as
    camkit.session.osd_shooting fetches it, into a file of this process's own, removed after, with camlink's .part), or
    "" when it cannot be fetched or read. folder: where that file goes while a row whose values are withheld is open
    (LiveCamera.osd_folder: a folder of the run's own, mode 0700), never the shared temporary folder then."""
    from .frames import load
    path = (Path(folder) / "press.png" if folder is not None
            else Path(tempfile.gettempdir()) / f"camkit_osd_{os.getpid()}_press.png")
    try:
        return screen.read(load(link.osd(path))).kind or ""
    except Exception:
        return ""
    finally:
        for left in (path, path.with_name(path.name + ".part")):
            with contextlib.suppress(OSError):
                left.unlink()


class _Rejudge(Exception):
    """Inside LiveCamera.press, nothing sent: the reader named the lit row on a frame by then older than STALE_S, and a
    fresh frame of the same screen is now the camera's, so the press is judged again on it from the top
    (LiveCamera.lit_by_reader); known, the label and the screen and lit row it was read on."""

    def __init__(self, known: dict):
        super().__init__("judged again on a fresh frame")
        self.known = known


class LiveCamera:
    def __init__(self, link, hdmi, run, may_open=(), network=(), screens: bool = False, options=None, values=None,
                 readings=None, owner=None, labels=None, look: bool = False):
        self.link, self.hdmi, self.run = link, hdmi, run
        # a look lap (a run given --network: kit/crawl_run.py, kit/drive.py; docs/decisions/0024): a never-open row opens
        # to look at, no decision naming it, but what safety.look_lap_refused refuses, and only where the lit bar is the
        # row its caller names for the press (press's row: bar_is_row), seen opened or under its first open; it is then
        # looked at as a row a network decision opened with no option named (look_row), and every screen's text is
        # withheld as on a --network run
        self.look = bool(look)
        log_to(run)                     # a reader that fails during the run is logged in its events.jsonl (camkit.vlm)
        self.may_open = frozenset(may_open)            # never-open rows this run was told it may open
        # the one row a dated owner decision opens for this run (kit/drive.py --owner, the last label of its --path):
        # {label: info} as safety.owner_decided gives it. It opens with Right alone, once (owner_opened); inside it only
        # up, down, MENU and Enter go out, and an Enter that is an action's step or confirmation, a never-choose option,
        # or the opening of a row that acts on opening goes out only when drive.py allowed that very press for that very
        # row (permit, used up by the next press) and safety.arm_refused passes on this camera's own reading too; after
        # an armed press only MENU (owner_done). A row whose values are withheld (safety.BLANKED) is MENU alone from its
        # opening, the eyes writing every frame of it black (blank), no reader asked. handed counts the presses handed
        # to the link
        self.owner = dict(owner or {})
        self.permit = None
        # owner_only: set by kit/drive.py once its walk to the owner row is done (press)
        self.owner_opened = self.owner_done = self.blank = self.owner_only = False
        self.handed = 0
        # the Wi-Fi and Bluetooth rows, address screens and identity rows a dated owner decision opens for this run
        # (--network: safety.network_decided's {row: date}), whether an address screen among them may open (kit/drive.py
        # alone: screens), the options the decision lets the kit choose in each ({row: [options]}: none, look only),
        # the values the kit knows for each (runner.network_values: a menu row's bar carries its value after its label)
        # and every reading the page model keeps of each (runner.network_readings: OCR glues a row's icon to its label).
        # While such a row is open (network_open, until network_left) only what safety.look_refused lets through goes
        # out; on an address screen (address_open) or a screen naming identity or credentials (identity_open), MENU
        # alone, and no reader is asked (camkit.vlm.HELD)
        self.network = dict(network) if isinstance(network, dict) else frozenset(network)
        # the labels the kit knows (runner.label_readings), against which a tail a lit bar carries after a decided row's
        # label, where no value of the row is known, must make no other label (safety.other_label); None: no such tail
        self.labels = labels
        self.screens = bool(screens)
        self.options = dict(options or {})
        self.values = dict(values or {})
        self.readings = dict(readings or {})
        self.network_open = self.address_open = self.identity_open = None
        # one row lifted for one press (kit/provers/pp_reset_run.py's Reset): a predicate (frame, lit) -> bool, set
        # by the caller for its next press and used up by that press; None (unset) changes nothing
        self.may_open_exact = None
        # the caller's word that it judged its next press with the confirmation check lifted (drive.py --owner --confirm):
        # used up by that press (confirm_refused). True, or the words naming it; or ("profile_reset", "PPn") for
        # pp_reset_run's question, which this camera judges again itself (profile_reset_passed)
        self.confirm_once = False
        # a prover's consent, named by its run's --allow for its own row, to answer that row's screen with its next press
        # (memreg_run's and framepos_run's slot screen, mymenu_run's picker, customshoot's Register): the screen's shape
        # no longer refuses that Enter, the word list still does (confirm_refused); the words naming it, used up likewise
        self.answer_once = None
        # the camera refused MENU on the screen read last ({"moves", "screen", "frame"}): the next Enter, on that very
        # screen with nothing sent between, may answer a notice whose OK is its only button (leave_notice)
        self.menu_refused = None
        self.frame = hdmi.grab("live-start")
        self.screen = self.reading(self.frame)
        self.screen.frame_path = self.frame.path.name
        self.presses = 0
        self._seen = self._moves()      # the link's count of screen-moving commands at the screen's last read

    def _moves(self) -> int:
        """The link's count of the commands sent that can move the screen (camkit.link.MOVES: a download, an upload,
        any press or dial, this camera's own among them); 0 for a link that keeps none."""
        return getattr(self.link, "moves", 0)

    def reading(self, f) -> screen.Screen:
        """The screen on frame `f` as this camera reads it, every reading of its own made here: camkit.screen's, its
        kind "playback" where it reads as the shooting screen while the camera says it is in Playback
        (camkit.session.playback_kind, docs/decisions/0021), so the walkers, drive.py and the link (which lets no key
        but MENU out there, and the Playback button only to leave it) see the playback view, never the shooting
        screen."""
        s = screen.read(f)
        s.kind = playback_kind(getattr(self, "link", None), s.kind)
        return s

    def _fresh(self, key: str):
        """The screen read afresh when something moved it since the last read without this camera seeing it (a
        download or an upload, a press sent straight through the link, proving.nav.to_shooting's own MENU presses): the
        link's count moved past the one kept at that read. A refresh, never a refusal; MENU needs none, since it is
        judged on no screen and the read after it is fresh."""
        if safety.canonical_input(key) in safety.SHOOTING_FREE or self._moves() == getattr(self, "_seen", self._moves()):
            return
        self.run.log("screen_stale", key=key, frame=self.frame.path.name, moves=self._moves())
        self.refresh("stale")

    def _recent(self, key: str):
        """The frame a press (or a dial) is judged on, and its settle measures "moved" from, looked at afresh when it is
        older than STALE_S: the screen can change with nothing sent (a menu drawn late, a notice gone, the camera
        leaving the menu by itself), so after a caller's sleep or a reader's call the screen read last may no longer be
        on show. 2026-11-18 (kit2_pass2 250526-250527): a MENU sent 4.7 s after the last read was judged, and settled,
        against that frame, a menu page that had opened meanwhile; the MENU closed it, the settle took the old menu
        page for its result, and the next Left reached the shooting screen. A frame younger than STALE_S, as every
        press's own settle leaves one, takes no extra grab. A frame that carries no capture time is left as it is."""
        t = getattr(self.frame, "t", None)
        if not isinstance(t, (int, float)) or t <= 0:
            return
        age = time.monotonic() - t
        if age <= STALE_S:
            return
        self.run.log("frame_stale", key=key, frame=getattr(self.frame.path, "name", None), age=round(age, 3))
        self.refresh("fresh")

    def press(self, key: str, allow=frozenset(), hold_ms=60, on_shooting=frozenset(), notice_ok: str = "",
              require_notice: bool = False, row=None, seen_enough: bool = False):
        """One press, read once it settles (look_late: seen_enough, a box prover's step, ends it on a change the settle
        saw). allow: the guarded buttons named (safety.GUARDED_INPUTS); on_shooting: the
        keys named for this press on the shooting screen, where a key does what the body makes of it (decision 21):
        a caller names a key there only where pressing it there is the point. notice_ok: the run's --info-ok for the
        notice on screen, which its caller judged (proving.screens.pass_named_notice): an Enter on that notice goes when
        it shows no question mark, its OK is plainly its only button and reads OK, and it reads as no confirmation
        (confirm_refused). require_notice: an Enter meant for the notice that has just refused MENU (leave_notice) and
        nothing else: refused unless the screen is that notice. row: on a look lap, the row the caller is about to
        open ({"expected", "seen", "first"}: bar_is_row), its first open counted only while its RESTORE_BY_HAND is on
        disk; None names none, and a never-open bar then opens on a look lap to no one's word. A press whose lit row
        the reader named (about a second) on a frame by then older than STALE_S is judged again from the top on a fresh
        frame, or refused where the screen changed (lit_by_reader); the one-press words below are spent once, here."""
        exact = getattr(self, "may_open_exact", None)
        if exact is not None:
            self.may_open_exact = None      # one press only, whatever it is
        permit = getattr(self, "permit", None)
        self.permit = None                  # drive.py's word for one owner press: used up by this press, whatever it is
        confirmed = getattr(self, "confirm_once", False) or False
        self.confirm_once = False           # a caller's confirmation check made for one press: used up by it likewise
        answer = getattr(self, "answer_once", None)
        self.answer_once = None             # a prover's consent for one press: used up likewise
        menu_refused = getattr(self, "menu_refused", None)
        self.menu_refused = None            # a refused MENU vouches for the press right after it alone
        known = None
        for _ in range(1 + REJUDGES):
            try:
                self._press(key, allow, hold_ms, on_shooting, notice_ok, require_notice, row, seen_enough,
                            (exact, permit, confirmed, answer, menu_refused), known)
                return
            except _Rejudge as again:
                known = again.known
        self.refuse(key, "the screen kept changing while the reader named its lit row: the press is not sent on a screen "
                         "nobody judged; read the screen again and choose afresh", changed=True)

    def _press(self, key: str, allow, hold_ms, on_shooting, notice_ok: str, require_notice: bool, row,
               seen_enough: bool, once: tuple, known):
        """press's judging, from the top, and the press sent once every guard passes. once: the one-press words press
        spent (may_open_exact, permit, confirm_once, answer_once, menu_refused); known: the lit row's label the reader
        gave on the pass before, with the screen and lit row it was read on (lit_by_reader), or None."""
        exact, permit, confirmed, answer, menu_refused = once
        arming = self.inside_refused(key, permit)       # inside a network row: look only, or MENU alone
        # a MENU, or an Enter inside_refused let through (an option the decision names), may close the row once it has
        # gone out: only then can the lock end (_inside_after)
        closes = getattr(self, "network_open", None) is not None and safety.canonical_input(key) in CLOSES
        self._fresh(key)                    # the screen the press is judged on is never one the camera has left
        self._recent(key)                   # nor one seen longer ago than STALE_S, nor measured from such a frame
        if safety.canonical_input(key) in safety.ENTER_KEYS | safety.TRASH_KEYS:
            # an Enter or a trash button: the screen looked at again, and that frame the one every check below judges
            # (look_before); a screen changed since its caller read it is refused (safety.ScreenChanged)
            self.look_before(key)
        # the never-open check judges the key as the guards read it (" right" and "Right" are Right), so a padded or
        # look-alike spelling never skips it; the link then refuses any spelling that is not the key's own name
        network, screens = getattr(self, "network", ()), getattr(self, "screens", False)
        values, opened, address, cls = getattr(self, "values", {}), None, False, None
        readings = getattr(self, "readings", {})
        owner, owner_row = getattr(self, "owner", None) or {}, None
        look = getattr(self, "look", False)
        if isinstance(row, dict):
            # the caller's first open counts only while its marker is on disk (camkit.first_open, kit/drive.py)
            row = {**row, "first": bool(row.get("first")) and self.first_open_under_way()}
        looked = {}                 # a row a look lap opens with no decision naming it: its bar, and whether it is blanked
        if safety.canonical_input(key) in OPENS and self.screen.kind in ROW_SCREENS:
            lit = lit_text(self.frame.image, self.frame.path)
            if not lit.strip() and lit_box(self.frame.image) is not None:
                lit = self.lit_by_reader(key, known)    # a bar OCR read nothing in: the reader names it, or no press
            why = open_refused(lit, self.may_open, network, screens, values, readings, getattr(self, "labels", None),
                               look, row)
            if why and owner and getattr(self, "network_open", None) is None:
                # the row an owner decision opens for this run, of the very class it was lifted from: Right alone, once
                owner_row = safety.owner_lifted_row(lit, owner, values)
                if owner_row is not None:
                    why, arming = self.owner_open_refused(key, owner_row, lit, permit)
            if why and exact is not None and not safety.never_lifted(lit) and not safety.network_words(lit) \
                    and exact(self.frame, lit):
                self.run.log("press_lifted_exact", key=key, frame=self.frame.path.name, lit=lit)
                why = ""
            if why:
                self.refuse(key, why, row=True)     # about the lit row itself: a crawl skips it (safety.RowRefused)
            if owner_row is not None:
                opened, cls = owner_row, owner[owner_row].get("class")
                address = cls == safety.LIFT_ADDRESS
            elif (network or look) and getattr(self, "network_open", None) is None:
                opened = safety.network_lifted_row(lit, network, screens, values, readings,
                                                   getattr(self, "labels", None)) if network else None
                cls = safety.lift_class(lit) if opened else None
                if opened is None and look:
                    # a row a look lap opens, no decision naming it: looked at as a decided row with no option named
                    bar = look_row(lit, values, getattr(self, "labels", None), row)
                    if bar is not None:
                        opened, cls = WITHHELD_ROW, safety.look_class(lit)
                        looked = {"bar": bar, "look": True, "blank": bool(
                            any(safety.look_blank(t) for t in (lit, *safety.row_judged(lit, values,
                                                                                       getattr(self, "labels", None)))))}
                address = cls == safety.LIFT_ADDRESS
        canon = safety.canonical_input(key)
        # the owner row lit on a screen read as no menu page: judged here too (owner_open_refused, whose screen check
        # refuses it), never by drive.py alone
        if owner and owner_row is None and getattr(self, "network_open", None) is None and canon in OPENS \
                and self.screen.kind not in ROW_SCREENS:
            lit = lit_text(self.frame.image, self.frame.path)
            row = safety.owner_lifted_row(lit, owner, values)
            if row is not None:
                why, _ = self.owner_open_refused(key, row, lit, permit)
                if why:
                    self.refuse(key, why)
        if getattr(self, "owner_only", False) and owner and canon in OPENS and owner_row is None \
                and getattr(self, "network_open", None) is None:
            # set by kit/drive.py once the walk to the owner row is done: from then no row opens but the owner row, and
            # no Enter goes out outside it, whatever the lit text reads as ("Formal" for Format: 2026-11-14, a review)
            self.refuse(key, "in an --owner run no row but the owner row opens and no Enter goes out outside it, and "
                             "the lit row does not read as the owner row (docs/decisions/0008)")
        if owner and canon in ("enter", "ms_enter"):
            self.wiping_refused(key, arming)    # Initialize's kin: this camera's own check, beside drive.py's
        confirming = canon in safety.ENTER_KEYS | safety.TRASH_KEYS
        judged_at = None
        self.box_reset_judged = False       # set by reset_passed for this one C4 alone
        if confirming:
            # what the screen asks, by its shape, on the screen on show now: this camera's own check, which nothing
            # pressing through it bypasses; judged_at, the link's count of moving commands when it looked
            judged_at = self.confirm_refused(key, permit, confirmed, answer=answer, notice_ok=notice_ok,
                                             menu_refused=menu_refused, require_notice=require_notice)
        judged = self.judged_screen(key)
        if self.box_reset_judged and canon == "c4":
            # a Custom box's size editor judged under its Reset consent (BoxReset): the link is handed the kind decision 7
            # names for it, for this C4 alone, where this screen's own (no known kind) is refused there
            judged, self.box_reset_judged = safety.C4_BOX_EDITOR, False
        t = time.monotonic()
        before = self.screen
        if arming:
            self.owner_done = True          # an armed press, once: from here only MENU, whatever answers it
            self.run.log("armed_press", key=key, frame=self.frame.path.name, row=arming[0], what=arming[1])
        # the safety allow-list, the STOP check, C4's screen check and the shooting screen's live there: the screen
        # read last goes with it; an Enter or a trash button carries the link's count of moving commands at the moment
        # its check looked at the screen (Link.press's judged), which the link refuses when anything has moved since
        self.handed = getattr(self, "handed", 0) + 1
        try:
            self.link.press(key, hold_ms, allow=allow, screen=judged, on_shooting=on_shooting,
                            **({"judged": judged_at} if confirming else {}))
        except CameraRefused:
            if canon == "menu":
                # the camera refused MENU on this screen: the next Enter, on it, may take a lone OK (leave_notice)
                self.menu_refused = {"moves": self._moves(), "screen": self.screen, "frame": self.frame.path.name}
                self.run.log("menu_refused", frame=self.frame.path.name)
            raise
        if closes:
            self.menu_went_out()
        if owner_row is not None:
            info = owner[owner_row]
            blank = safety.blanked(cls, info.get("logged"))
            self.owner_opened = True
            self.network_open = {"row": owner_row, "address": address, "class": cls, "frame": self.frame.path.name,
                                 "from": before, "closing": False, "menus": getattr(self.link, "menus", None),
                                 "owner": True, "blank": blank, "logged": bool(info.get("logged"))}
            self.run.log("owner_row_opened", key=key, frame=self.frame.path.name, row=owner_row, lifted_from=cls,
                         blank=blank)
            if blank or address or cls == safety.LIFT_SERIAL:
                self.identity_open = self.frame.path.name       # MENU alone from its opening
            if blank:
                self.blank_row()                # before the frame it opened is settled and saved
            opened = None
        if opened is not None:
            # a row a network decision opens: from here, whatever its screen reads as, look only (inside_refused), and
            # on an address screen MENU alone, no reader asked, until a MENU (or an Enter on a named option) has gone
            # out and the page it was opened from, or the shooting screen, is back (_inside_after). "menus": the
            # link's count of MENU presses now, so that a MENU sent past this camera (a cleanup press) counts too. A
            # row a look lap opened with no decision naming it alike, with no option named ("look"; its bar as read,
            # "bar", which ends the lock); what the owner route blanks blanked from its opening as there
            # (safety.look_blank, docs/decisions/0024)
            self.network_open = {"row": opened, "address": address, "class": cls, "frame": self.frame.path.name,
                                 "from": before, "closing": False, "menus": getattr(self.link, "menus", None),
                                 **looked}
            self.run.log("network_row_opened", key=key, frame=self.frame.path.name, row=opened, lifted_from=cls,
                         **({"look": True, "blank": looked["blank"]} if looked else {}))
            if looked.get("blank"):
                self.identity_open = self.frame.path.name       # MENU alone from its opening
                self.blank_row()                # before the frame it opened is settled and saved
            if address:
                self.address_open = self.frame.path.name
                vlm.HELD = "an address screen is open"
                self.run.log("address_screen_opened", key=key, frame=self.frame.path.name)
        # every press expects a change: a press that seems ignored gets a full second before it counts
        # as "nothing happened" (Picture Profile: a Down showed no change within 0.5 s, 2026-10-28)
        self.pressed_from = self.frame          # the frame the press was made on (proving.screens.title_settled)
        try:
            f, moved = self.hdmi.settle(self.frame, key, expect_change=True, sent_at=t)
            self.frame, self.screen = f, self.reading(f)
            self.rest(f"{key}-rest")
            f = self.look_late(key, before, moved, seen_enough)
            if canon == "menu" and getattr(judged, "kind", None) == "shooting":
                f = self.menu_watch(t, f)       # its result a menu page if one shows within MENU_LATE s of the press
        except LinkError as e:
            # the key went: a screen read through the link that fails now (OSD eyes: "no OSD image", a dropped session)
            # is no refusal of it, so nobody sends it again or takes it as not gone (live.press, kit/drive.py's armed
            # press; 2026-11-18, the review's finding 1). The next press reads the screen afresh (_fresh)
            why = f"{key}: the press went, and its screen could not be read afterwards ({type(e).__name__}: {e})"
            self.run.log("press_unread", key=key, why=f"{type(e).__name__}")
            raise LinkError(why) from e
        self.screen.frame_path = f.path.name          # evidence: which saved frame this screen is
        self.presses += 1
        self._seen = self._moves()
        self.run.log("press", key=key, frame=f.path.name, screen=self.screen.kind, moved=moved,
                     timing=self.hdmi.timing)
        self._inside_after()

    def look_late(self, key: str, before, moved: bool, seen_enough: bool = False):
        """After a press settled: where its screen reads in the state it had before, look again a little later; the
        frame the press ends on. Live view behind a dialog that previews each option (Picture Profile) keeps changing,
        which can end the settle before the cursor has moved (2026-10-28). OK that applies a setting can hold the OSD
        image for about 3 s while the camera applies it (Drive Mode's self-timer over the OSD, 2026-11-06: the record
        had changed and the row page was back, the picture of it came 3.25 s after the press, where HDMI showed it in
        0.2 s): OK is given OK_LATE in all, a look every half second. seen_enough: a box prover's step of a box's value
        (kit/provers/optboxes_run.py, boxes_run.py), whose screen has no live view behind it and whose state does not
        hold the value, so that every step read as nothing happened and waited 0.5 s (201 of 285 presses, 2026-11-18):
        there a change the settle saw (`moved`) is the press's, and no look again goes; a step whose change was not
        seen still gets it. Never the default."""
        f = self.frame
        if not screen.same_state(self.screen, before) or (seen_enough and moved):
            return f
        end = time.monotonic() + (OK_LATE if key == "enter" else 0.5)
        while True:
            time.sleep(0.5)
            f2 = self.hdmi.grab(f"{key}-late", save=False)
            s2 = self.reading(f2)
            if not screen.same_state(s2, before):
                keep(f2, self.run.shot_path(f"{key}-late"), getattr(self, "blank", False))
                f, self.frame, self.screen = f2, f2, s2
                return f
            if time.monotonic() >= end:
                return f

    def menu_watch(self, sent_at: float, f):
        """After a MENU judged on the shooting screen whose settle ended on no menu page (the shooting screen's own
        redraw can end it before the menu is drawn: kit2_pass2 250525-250527, 2026-11-18), with HDMI eyes: the frames
        watched (glance, unsaved) until one reads as a menu page or MENU_LATE s have passed since the press (sent_at),
        and the press's result taken from that menu page, else from the last frame watched; saved as evidence, logged
        ("menu_watch": seen or not, after how long). The helper's own look (menu_check) then looks no more
        (menu_watched). OSD eyes, whose picture lags the screen, unchanged: the frame the press settled on (`f`)."""
        if getattr(self.hdmi, "name", "") != "hdmi" or getattr(self.screen, "kind", None) in MENU_PAGES:
            return f
        last = None
        while time.monotonic() - sent_at < MENU_LATE:
            time.sleep(MENU_POLL)
            last = self.glance("menu-watch")
            if last[1].kind in MENU_PAGES:
                break
        if last is not None:
            f, self.screen = last
            keep(f, self.run.shot_path("menu-watch"), getattr(self, "blank", False))
            self.frame = f
            self.rest("menu-watch-rest")    # a menu caught sliding in is looked at again until it stops
            f = self.frame
        self.menu_watched = f
        self.run.log("menu_watch", frame=f.path.name, seen=getattr(self.screen, "kind", None) in MENU_PAGES,
                     after=round(time.monotonic() - sent_at, 3))
        return f

    def first_open_under_way(self) -> bool:
        """Whether the camera's RESTORE_BY_HAND is on disk for this run's camera (camkit.runs.restore_pending_any;
        camkit.first_open and kit/drive.py write it before a first open): with the caller's word for the very row (press's
        row), that row's first open is under way; alone it says nothing of any row."""
        from .runs import restore_pending_any
        root = getattr(getattr(self, "run", None), "root", None)
        return root is not None and restore_pending_any(root) is not None

    def blank_row(self) -> None:
        """A row whose values are withheld has just been opened (an owner row of safety.BLANKED, or such a row a look lap
        opened: safety.look_blank): the eyes write every frame of it black from here (withhold) and no reader is asked (camkit.vlm.HELD),
        until the row is left (_inside_after)."""
        self.withhold(True)
        vlm.HELD = "a row whose values are withheld is open"

    def withhold(self, on: bool) -> None:
        """While a row whose values are withheld is open (blank): the eyes save every frame black and poll the camera's
        own picture outside the run's folder (camkit.frames' withheld), so no pixel of its screens is written as
        evidence; the frames in memory keep their pictures, for the screen's kind alone."""
        self.blank = bool(on)
        with contextlib.suppress(AttributeError):
            self.hdmi.withheld = bool(on)
        if not on:
            # the eyes' folder for the camera's own picture of those screens goes with them (camkit.frames), and this
            # camera's own (osd_folder)
            getattr(self.hdmi, "close_private", lambda: None)()
            d, self._private = getattr(self, "_private", None), None
            if d is not None:
                shutil.rmtree(d, ignore_errors=True)

    def osd_folder(self):
        """Where the camera's own picture of the screen is fetched to (osd_kind) while a row whose values are withheld is
        open: the OSD eyes' own folder (camkit.frames' private_dir), or, with eyes that have none (HDMI), one of this
        camera's own (tempfile.mkdtemp, mode 0700), removed when the row is left or the process ends; never the shared
        temporary folder then. None otherwise."""
        if not getattr(self, "blank", False):
            return None
        made = getattr(self.hdmi, "private_dir", None)
        if made is not None:
            return made()
        d = getattr(self, "_private", None)
        if d is None or not Path(d).is_dir():
            d = self._private = Path(tempfile.mkdtemp(prefix="camkit_osd_"))
            atexit.register(shutil.rmtree, d, True)
        return d

    def osd_seen(self) -> str:
        """The kind the camera's own picture of the screen reads as (osd_kind), fetched into osd_folder while a row
        whose values are withheld is open."""
        folder = self.osd_folder()
        return osd_kind(self.link) if folder is None else osd_kind(self.link, folder)

    def owner_open_refused(self, key: str, row: str, lit: str, permit) -> tuple:
        """(why a press may not open the owner row `row` whose lit text is `lit`, or "", the row when the press is an
        armed one): Right alone (never Enter, the multi-selector or a look-alike), once per run (owner_opened), never
        after an armed press; a row that acts on opening only when drive.py allowed that very opening for that very row
        (`permit`: {"row", "what": "open"}) and safety.arm_refused passes on this camera's reading."""
        if safety.name_refused(key) or safety.canonical_input(key) != "right":
            return f"the owner decision opens {row!r} with Right alone, never {key!r} (docs/decisions/0008)", None
        if getattr(self, "owner_opened", False) or getattr(self, "owner_done", False):
            return "one owner row per run, opened once: this run has opened it already (docs/decisions/0008)", None
        if self.screen.kind not in safety.ROW_PAGES:
            return f"the owner row is opened from a menu page alone, not a {self.screen.kind!r} screen", None
        info = self.owner.get(row) or {}
        if not info.get("acts_on_open"):
            return "", None
        if not isinstance(permit, dict) or permit.get("row") != row or permit.get("what") != "open":
            return (f"{row!r} acts as soon as it opens, and drive.py did not allow this opening as the armed last "
                    "press of the run (docs/decisions/0008)"), None
        why = safety.arm_refused(row, info.get("class"), "open", self.screen.kind, lit, "", info.get("confirm", False),
                                 info.get("link_loss", False), place=info.get("path"))
        return why, (None if why else (row, "open"))

    def wiping_refused(self, key: str, arming) -> None:
        """Refused, logged, for an Enter on a run given an owner row, this camera's own check beside drive.py's
        NEVER_ENTER: never on a lit text reading Initialize, Reset Network Set. or SSID/PW Reset; never on a screen
        reading one of them unless the lit text is Camera Settings Reset, or the press is the run's armed confirmation
        of that very action (`arming`: (row, what), safety.armed_wiping)."""
        lit, text = lit_text(self.frame.image, self.frame.path), text_of(self)
        if any(safety.LINK_WIPING_ENTER.search(r) for r in safety.readings(lit)):
            self.refuse(key, f"the cursor is on {lit.strip()!r} (docs/decisions/0005)")
        m = next((m for r in safety.readings(text) for m in [safety.LINK_WIPING_ENTER.search(r)] if m), None)
        armed = arming[0] if arming and arming[1] in ("confirm", "final") else ""
        if m and not safety.CAMERA_SETTINGS_RESET.search(lit) and not safety.armed_wiping(armed, m.group(0)):
            self.refuse(key, f"the screen reads {m.group(0)!r} and the press is no armed confirmation of that very "
                             "action (docs/decisions/0005)")

    def confirm_refused(self, key: str, permit, confirmed, answer=None, notice_ok: str = "", menu_refused=None,
                        require_notice: bool = False) -> int:
        """Refused, logged, for an Enter (or the multi-selector's centre, or the trash button) on a screen that asks or
        may ask, judged by its shape and never by what it is called (safety.enter_refused, 2026-11-14): a notice, a
        screen of no known kind, one whose text cannot be read or reads nothing, one that shows a question mark above
        its footer (body_of), a carousel that asks (safety.asks). This camera's own check, which every walker, prover
        and drive.py press goes through, beside drive.py's, so that the lower layer rests on no caller's (2026-11-14, two
        reviews). Until 2026-11-14 it only gated a list of English words (safety.confirmation_refused), and a question
        that held none ("Clear registered faces? OK Cancel"), or any question on a camera not set to English, passed.
        The screen it judges is the one press looked at again just before (look_before: one fresh grab, on OSD eyes once
        OSD_LAG has passed since the kit's last move, its text read afresh), so a question the camera raised by itself, a
        popup drawn after the settle, or an overlay that leaves the screen's kind and structure as they were, is never
        answered on an older reading; a screen that changed since its caller read it was refused there
        (safety.ScreenChanged). Returns the link's count of moving commands at that look, which the press carries
        (Link.press's judged) and the link checks again.
        The explicit ways past, each named by its caller and logged ("enter_passed"):
        - `confirmed` (confirm_once): the caller judged this very press with every check lifted: the owner route
          (drive.py --owner --confirm, for a step or the armed press it allowed, beside `permit`); `permit`: drive.py
          allowed it as an owner row's step or armed press (owner_inside_refused). ("profile_reset", "PPn"),
          pp_reset_run's one question under its --allow, lifts nothing by itself: the screen read afresh here must be
          that profile's own reset question (safety.profile_reset_dialog), else no Enter;
        - `answer` (answer_once): a consent named for one press on one named screen (a prover's --allow for its own
          row's screen; drive.py's and card_actions.py's --confirm with the screen's whole text): the shape refuses
          nothing, the word list still refuses a confirmation; an UprightDialog, for an Enter on a screen of no known
          kind alone: that one Enter judged as a level dialog's on the frame read upright (upright_passed), and on any
          other screen or key it answers nothing; a BoxEditor likewise, that one Enter (a Custom box's size editor's
          OK) judged on the editor's own shape and the words above its footer (editor_passed); a BoxReset, that one C4
          (the editor's Reset) judged so, the link then handed decision 7's size editor kind (reset_passed); a TwoBoxes,
          that one Enter (the OK that leaves a row's two-box screen) judged on that screen's own shape and the words
          above its footer (boxes_passed); an OptionBoxes, that one Enter (the OK that keeps a list option's lit box)
          judged on its title, the lit box's word and value and the drawn OK key (option_passed); a PanelSlider, that
          one Enter (the OK that keeps a panel's slider) judged on the panel's own shape and the words above its footer
          (panel_passed);
        - on a notice, `notice_ok` (the run's --info-ok, which proving.screens.pass_named_notice judged), or
          `menu_refused`: the camera refused MENU on this very screen with nothing sent since (leave_notice); either goes
          only where the notice's lit button reads OK, is plainly its only one (lone_of: safety.lone_ok) and its text
          reads as no confirmation. `require_notice` (leave_notice's OK): refused unless the screen is that notice,
          passed so.
        A carousel reads as a dialog too (screen.classify: its divider) and asks nothing: Enter on it chooses the lit
        option, which the provers prove on rows whose own title holds a confirmation's word (32 of the a1 II
        definition's 3,584 carousel texts: Delete confirm., File Name Format, Custom Key Setting's Delete, File Number's
        Reset...); its lit option is read on its title line where lit_text finds the selected icon (title_of)."""
        canon = safety.canonical_input(key)
        armed = isinstance(permit, dict) and permit.get("what") in ARMED_WHATS
        kind = self.screen.kind
        judged_at = self._moves()
        if isinstance(confirmed, tuple):
            return self.profile_reset_passed(key, confirmed, judged_at)
        by = (confirmed if isinstance(confirmed, str) else "--confirm") if confirmed else \
            ("an owner decision's armed press" if armed else "")
        if by and not require_notice:
            self.run.log("enter_passed", key=key, frame=self.frame.path.name, screen=kind, by=by)
            return judged_at
        try:
            text, body = text_of(self), body_of(self)
            lit = lit_text(self.frame.image, self.frame.path) if canon in safety.ENTER_KEYS else ""
            if kind == "dialog" and canon in safety.ENTER_KEYS and not lit.strip():
                lit = title_of(self)        # the carousel's lit option on its title line
        except Exception as e:
            self.refuse(key, f"the {kind} screen's text cannot be read ({type(e).__name__}), so whether it asks cannot "
                             "be told")
        passed, lone = "", None
        if safety.first_time_screen(kind, text):
            kind = "notice"         # a first-time screen (no notice's frame lines, a "Don't show this again." box)
        if isinstance(answer, UprightDialog | BoxEditor | TwoBoxes | OptionBoxes | PanelSlider):
            consent, answer = answer, None      # a portrait dialog's, a size editor's, a two-box screen's, an option's
            if kind == "unknown" and canon in safety.ENTER_KEYS and not require_notice:  # boxes' or a panel's slider's
                passed_by = {UprightDialog: self.upright_passed, BoxEditor: self.editor_passed,   # consent answers it
                             TwoBoxes: self.boxes_passed, OptionBoxes: self.option_passed,       # alone
                             PanelSlider: self.panel_passed}[type(consent)]
                return passed_by(key, consent, judged_at)
        if isinstance(answer, BoxReset):
            consent, answer = answer, None      # a size editor's Reset consent answers its C4 alone
            if kind == "unknown" and canon == "c4" and not require_notice:
                return self.reset_passed(key, consent, judged_at)
        if kind == "notice" and canon in safety.ENTER_KEYS:
            if notice_ok:
                passed = f"--info-ok {notice_ok}"
            elif isinstance(menu_refused, dict) and menu_refused.get("moves") == self._moves() \
                    and same_screen(self.screen, menu_refused.get("screen")):
                passed = MENU_REFUSED
            if passed:
                lone = lone_of(self.frame.image, self.frame.path)
        if require_notice and passed != MENU_REFUSED:
            self.refuse(key, f"this OK was meant for a notice that had just refused MENU, and the screen ({kind}) is not "
                             "that notice: no Enter")
        why = safety.enter_refused(kind, text, lit, body, passed, lone, key=canon)
        if why and answer and not require_notice and str(text or "").strip():
            # a consent named for this press on its own named screen: the shape refuses nothing, the word list still
            # does (a screen that reads nothing gives the words nothing to judge: no consent answers it)
            said = safety.confirmation_refused(text)
            if not said:
                self.run.log("enter_passed", key=key, frame=self.frame.path.name, screen=kind, by=str(answer))
                return judged_at
            why = f"{why}; and it reads as a confirmation ({said}), which {answer} does not answer"
        if why:
            self.refuse(key, f"{why}. Enter on such a screen goes only by an explicit way past: the owner route "
                             "(drive.py --owner --confirm), a consent named for this screen (a prover's --allow, "
                             "--confirm with the screen's text), a notice --info-ok names, or a lone OK on a notice "
                             "that has just refused MENU")
        if passed:
            self.run.log("enter_passed", key=key, frame=self.frame.path.name, screen=kind, by=passed)
        return judged_at

    def upright_passed(self, key: str, consent: UprightDialog, judged_at: int) -> int:
        """An Enter on a screen of no known kind under a portrait dialog's consent (UprightDialog): the frame judged
        (look_before's) read upright by the consent's reader, its title the row's own (safety.clean_label, the icon OCR
        reads before it left out), then judged as a level dialog's Enter on that reading (safety.enter_refused as a
        dialog: text read, no question mark above the footer, asks() on the lit option) and by the confirmation words,
        which every consent keeps. Refused, logged, on any of them, or where the reading fails; passed, logged with the
        consent's words. Returns judged_at."""
        try:
            title, lit, text, body = consent.read(self)
        except Exception as e:
            self.refuse(key, f"{consent.name}: the frame read upright cannot be read ({type(e).__name__}), so whether it "
                             "asks cannot be told")
        if not safety.clean_label(title) or safety.clean_label(title) != safety.clean_label(consent.row):
            self.refuse(key, f"{consent.name}: its title read upright ({str(title or '').strip()[:40]!r}) is not "
                             f"{consent.row}'s: no Enter")
        why = safety.enter_refused("dialog", text, lit, body, key=safety.canonical_input(key))
        said = "" if why else safety.confirmation_refused(text)
        if why or said:
            self.refuse(key, f"{consent.name}, read upright: {why or f'it reads as a confirmation ({said})'}: no Enter")
        self.run.log("enter_passed", key=key, frame=self.frame.path.name, screen=self.screen.kind, by=consent.name)
        return judged_at

    def reset_passed(self, key: str, consent: BoxReset, judged_at: int) -> int:
        """A C4 on a screen of no known kind under a size editor's Reset consent (BoxReset): judged as editor_passed
        judges the editor's OK (its own shape, then the confirmation words above its footer); passed, the press hands
        the link decision 7's size editor kind for this C4 alone (box_reset_judged). Returns judged_at."""
        self.editor_passed(key, consent, judged_at)
        self.box_reset_judged = True
        return judged_at

    def option_passed(self, key: str, consent: OptionBoxes, judged_at: int) -> int:
        """An Enter on a screen of no known kind under a list option's boxes' consent (OptionBoxes): the frame judged
        (look_before's) read (boxes_lines) and judged by that screen's own shape and words (option_boxes_refused).
        Refused, logged, on any of them, or where the reading fails; passed, logged with the consent's words."""
        try:
            lines = boxes_lines(self)
        except Exception as e:
            self.refuse(key, f"{consent.name}: the screen cannot be read ({type(e).__name__}), so whether it asks cannot "
                             "be told")
        why = option_boxes_refused(consent, lines, self.frame.image)
        if why:
            self.refuse(key, f"{consent.name}: {why}: no Enter")
        self.run.log("enter_passed", key=key, frame=self.frame.path.name, screen=self.screen.kind, by=consent.name)
        return judged_at

    def boxes_passed(self, key: str, consent: TwoBoxes, judged_at: int) -> int:
        """An Enter on a screen of no known kind under a row's two-box consent (TwoBoxes): the frame judged
        (look_before's) read (boxes_lines) and judged by that screen's own shape (two_boxes_refused), then by the
        confirmation words on what stands above its footer, which every consent keeps. Refused, logged, on any of them,
        or where the reading fails; passed, logged with the consent's words. Returns judged_at."""
        try:
            lines = boxes_lines(self)
        except Exception as e:
            self.refuse(key, f"{consent.name}: the screen cannot be read ({type(e).__name__}), so whether it asks cannot "
                             "be told")
        why = two_boxes_refused(consent, lines, self.frame.image)
        said = "" if why else safety.confirmation_refused(ocr.text_in(lines, (0, 0, 640, FOOTER_TOP)))
        if why or said:
            self.refuse(key, f"{consent.name}: {why or f'it reads as a confirmation ({said})'}: no Enter")
        self.run.log("enter_passed", key=key, frame=self.frame.path.name, screen=self.screen.kind, by=consent.name)
        return judged_at

    def panel_passed(self, key: str, consent: PanelSlider, judged_at: int) -> int:
        """An Enter on a screen of no known kind under a panel slider's consent (PanelSlider): the frame judged
        (look_before's) read and judged by the panel's own shape (panel_slider_refused), then by the confirmation words
        on what stands above its footer, which every consent keeps. Refused, logged, on any of them, or where the reading
        fails; passed, logged with the consent's words. Returns judged_at."""
        try:
            lines = boxes_lines(self)
        except Exception as e:
            self.refuse(key, f"{consent.name}: the screen cannot be read ({type(e).__name__}), so whether it asks cannot "
                             "be told")
        why = panel_slider_refused(consent, lines, self.frame.image)
        said = "" if why else safety.confirmation_refused(ocr.text_in(lines, (0, 0, 640, FOOTER_TOP)))
        if why or said:
            self.refuse(key, f"{consent.name}: {why or f'it reads as a confirmation ({said})'}: no Enter")
        self.run.log("enter_passed", key=key, frame=self.frame.path.name, screen=self.screen.kind, by=consent.name)
        return judged_at

    def editor_passed(self, key: str, consent: BoxEditor | BoxReset, judged_at: int) -> int:
        """An Enter on a screen of no known kind under a size editor's consent (BoxEditor): the frame judged
        (look_before's) read as the editor (editor_texts) and judged by its own shape (box_editor_refused), then by the
        confirmation words on what stands above its footer, which every consent keeps (the footer's Reset is the editor's
        own button). Refused, logged, on any of them, or where the reading fails; passed, logged with the consent's
        words. Returns judged_at."""
        try:
            title, body, footer = editor_texts(self)
        except Exception as e:
            self.refuse(key, f"{consent.name}: the screen cannot be read ({type(e).__name__}), so whether it asks cannot "
                             "be told")
        why = box_editor_refused(consent.box, title, body, footer)
        said = "" if why else safety.confirmation_refused(body)
        if why or said:
            self.refuse(key, f"{consent.name}: {why or f'it reads as a confirmation ({said})'}: no Enter")
        self.run.log("enter_passed", key=key, frame=self.frame.path.name, screen=self.screen.kind, by=consent.name)
        return judged_at

    def look_before(self, key: str) -> None:
        """Before an Enter or a trash button is judged: the screen looked at again (look_again: one fresh grab, on OSD eyes
        once OSD_LAG has passed since the link's last move, Link.moved_at) and that frame made the one judged
        (judge_fresh), so every check of the press, the never-open row's and what the screen asks among them, reads it.
        Refused, logged, when no frame could be grabbed or read; and when the screen changed since its caller read it
        (safety.ScreenChanged, the fresh frame and reading kept): the caller chose the press, and judged its words, on
        the screen it read, so the press is never sent on another (2026-11-14, a third review: it was judged as it now
        was, and the proof recorded the old screen's choice). When the fresh frame is the caller's own picture, pixel
        for pixel, the caller's frame stays (its text, read already, is not read again)."""
        stale, fresh = look_again(getattr(self, "hdmi", None), self.screen, key, getattr(self.link, "moved_at", None))
        if stale and fresh is None:
            self.refuse(key, stale)
        if fresh is None or same_picture(fresh, self.frame):
            return
        self.judge_fresh(fresh, key, changed=bool(stale))
        if stale:
            self.refuse(key, f"{stale}; read the screen again and choose afresh", changed=True)

    def judge_fresh(self, f, key: str, changed: bool = False) -> None:
        """The frame look_again grabbed before a press made the one it is judged on: saved as evidence (black on a row
        whose values are withheld, as every frame then), read, its text read afresh by whoever reads it next. changed:
        the screen is not the state its caller read (logged)."""
        keep(f, self.run.shot_path(f"{key}-judged"), getattr(self, "blank", False))
        self.frame, self.screen = f, self.reading(f)
        self.screen.frame_path = f.path.name
        if changed:
            self.run.log("screen_changed_before_press", key=key, frame=f.path.name, screen=self.screen.kind)

    def profile_reset_passed(self, key: str, confirmed: tuple, judged_at: int) -> int:
        """pp_reset_run's way past, ("profile_reset", "PPn"): the Enter goes only where the screen read afresh here is
        that profile's own reset question (safety.profile_reset_dialog), so the lift covers that question alone and no
        free words a caller writes lift every check. Anything else is refused.
        In the final design the destructive word list keeps "reset" and is lifted only by the owner's typed word: this
        question must then either be carved out of it by this exact match or move to the owner route (not decided
        here, 2026-11-14)."""
        what, profile = (tuple(confirmed) + ("", ""))[:2]
        if what != "profile_reset":
            self.refuse(key, f"{confirmed!r} is no way past this camera knows: no Enter")
        try:
            why = safety.profile_reset_dialog(text_of(self), str(profile))
        except Exception as e:
            why = f"its text cannot be read ({type(e).__name__})"
        if why:
            self.refuse(key, f"the screen is not {profile}'s own reset question ({why}): no Enter")
        self.run.log("enter_passed", key=key, frame=self.frame.path.name, screen=self.screen.kind,
                     by=f"pp_reset_run --allow: {profile}'s own reset question, read again at the press")
        return judged_at

    def owner_inside_refused(self, key: str, inside: dict, permit):
        """Refused, logged, for a key that may not go out inside the owner row open (inside), else the row when the
        press is an armed one (an action's confirmation, a never-choose option), else None. Only up, down, MENU and
        Enter, each in its own spelling (safety.OWNER_KEYS_INSIDE); after an armed press, or on a screen that takes MENU
        alone (identity_open: a blanked row, an address or serial number screen, a keyboard, credentials), MENU alone.
        An Enter is what safety.owner_enter reads it as on this camera's own reading of the screen; a step, a
        confirmation or a never-choose option goes only when drive.py allowed that very press for that very row
        (`permit`: {"row", "what"}) and safety.arm_refused passes on this reading too."""
        self._fresh(key)                    # judged on a screen the camera has not left
        canon, row, cls = safety.canonical_input(key), inside["row"], inside.get("class")
        if safety.name_refused(key) or canon not in safety.OWNER_KEYS_INSIDE:
            self.refuse(key, f"{key!r} never goes out inside {row!r}, a row an owner decision opened: only up, down, "
                             "MENU and Enter (docs/decisions/0008)")
        if canon == "menu":
            return None
        if getattr(self, "owner_done", False):
            self.refuse(key, "the armed press of the run has gone: no key but MENU (docs/decisions/0008)")
        if inside.get("address") or getattr(self, "identity_open", None):
            self.refuse(key, f"a screen that takes MENU alone is open inside {row!r} (on {self.identity_open or 'it'}): no "
                             "key but MENU (docs/decisions/0008)")
        if canon != "enter":
            return None
        info = self.owner.get(row) or {}
        lit, text, kind = lit_text(self.frame.image, self.frame.path), text_of(self), self.screen.kind
        why, what = safety.owner_enter(row, cls, kind, lit, text, info.get("options") or (), info.get("steps_seen") or ())
        if not why and what == "step" and isinstance(permit, dict) and permit.get("what") == "final":
            what = "final"                  # a seen step drive.py arms as the last Enter of its run: armed here too
        if not why and what != "option":
            if not isinstance(permit, dict) or permit.get("row") != row or permit.get("what") != what:
                why = f"drive.py did not allow this press ({what}) inside {row!r} (docs/decisions/0008)"
            else:
                why = safety.arm_refused(row, cls, what, kind, lit, text, info.get("confirm", False),
                                         info.get("link_loss", False))
        if why:
            self.refuse(key, why)
        return (row, what) if what in ("confirm", "choose", "final") else None

    def inside_refused(self, key: str, permit=None):
        """Refused, logged, for a key that may not go out while a row a network decision opened is open
        (network_open): on an address screen or a screen naming identity or credentials, any key but MENU; else what
        safety.look_refused refuses (anything but up, down, MENU, and Enter on an option the decision names, read off
        the lit bar now). Whatever kind the screen reads as. Inside a row an owner decision opened, owner_inside_refused
        judges it instead, and its answer (the row, for an armed press) is returned."""
        inside = getattr(self, "network_open", None)
        if inside is None:
            return None
        if inside.get("owner"):
            return self.owner_inside_refused(key, inside, permit)
        canon = safety.canonical_input(key)
        if inside["address"] or getattr(self, "identity_open", None):
            why = "" if canon in safety.SHOOTING_FREE else (
                f"{'an address screen' if inside['address'] else 'a screen naming identity or credentials, or of no known kind,'}"
                f" is open (on {getattr(self, 'address_open', None) or self.identity_open}): no key but MENU goes out on it "
                "(docs/decisions/0008)")
        else:
            lit = lit_text(self.frame.image, self.frame.path) if canon in ("enter", "ms_enter") else ""
            # a row a look lap opened with no decision naming it takes no option, whatever is named (docs/decisions/0024)
            why = safety.look_refused(key, lit, inside["row"], None if inside.get("look") else
                                      getattr(self, "options", {}).get(inside["row"]))
        if why:
            self.refuse(key, why)

    def refuse(self, key: str, why: str, row: bool = False, changed: bool = False) -> None:
        """A press refused: logged in the run's events.jsonl and raised (safety.Refused; safety.RowRefused where `row`:
        the lit row itself may not be opened, which a crawl skips; safety.ScreenChanged where `changed`: the screen is
        not the state the caller read, look_before). On a --network run (network given) the reason's quoted texts are
        withheld in both, since a row's bar can carry an identity value (a device's name, an SSID, an address):
        safety.quoted_withheld."""
        said = safety.quoted_withheld(why) if getattr(self, "network", None) or getattr(self, "owner", None) or getattr(self, "look", False) else why
        self.run.log("press_refused", key=key, frame=self.frame.path.name, why=said)
        kind = safety.ScreenChanged if changed else safety.RowRefused if row else safety.Refused
        raise kind(f"{key}: {said}")

    def menu_went_out(self) -> None:
        """A MENU (or an Enter inside_refused let through) has gone out while a row a network decision opened is open:
        the next read may end the lock, if it shows the row's page again (network_left, which spends this). Called by
        press, by cancel_to_menu and by close (live.close), for the MENU presses they send past press."""
        inside = getattr(self, "network_open", None)
        if inside is not None:
            inside["closing"] = True

    def network_left(self) -> bool:
        """Whether the row a network decision opened has been left: a MENU, or an Enter on an option the decision names,
        has gone out just before this read (menu_went_out, or the link's count of MENU presses moved on), AND the screen
        is the shooting screen (menu_closed), or the page the row was opened from (same_position) with its lit bar reading
        the row itself, as its label or as the reading with its page's icon glued on that opened it (safety.bar_on_row; a
        popup over the dimmed page lights an option, never the row; a bar that cannot be read keeps the lock).
        The evidence of that MENU or Enter is used once: whatever this read says, it is spent here, so the release is
        judged on the screen read right after the closing key and never on a later one (a MENU the camera ignored, then
        a Down onto a frame that reads as the page, ends nothing). Never on a screen's kind alone: a camera slow to draw
        the row's list still shows the page after the press that opened it, and a list misread as a menu page reads as
        one; MENU that lands on another page leaves the lock as it is, and another MENU closes the menu."""
        inside = getattr(self, "network_open", None)
        if inside is None:
            return True
        closing = self.closing_seen(inside)
        inside["closing"], inside["menus"] = False, getattr(self.link, "menus", None)   # spent: a later read needs a new MENU
        if not closing:
            return False
        if getattr(self.screen, "kind", None) == "shooting":
            return self.menu_closed(inside)
        if inside.get("blank"):
            return False                        # its frames are not read: the shooting screen alone ends the lock
        try:
            if not screen.same_position(self.screen, inside["from"]):
                return False
            lit = lit_text(self.frame.image, self.frame.path)
        except Exception:                       # a screen or a bar that cannot be read is no way out
            return False
        # the bar on the row itself: its label, or a reading of it with its page's icon glued on that opened it
        # (safety.bar_on_row: "LANIP Address Setting" still reads so after MENU), or that icon as the live bar shows it
        # where the run knows its labels (the icon read with a letter misread, glued on or set apart: icon_slip)
        return safety.bar_on_row(lit, inside.get("bar") or inside["row"], getattr(self, "readings", {}),
                                 getattr(self, "labels", None))

    def closing_seen(self, inside: dict) -> bool:
        """Whether a MENU, or an Enter on an option the decision names, has gone out since the screen was last judged
        inside the row (menu_went_out, or the link's count of MENU presses moved on), without spending it."""
        menus = getattr(self.link, "menus", None)
        return bool(inside.get("closing")) or (isinstance(menus, int) and isinstance(inside.get("menus"), int)
                                               and menus > inside["menus"])

    def menu_closed(self, inside: dict) -> bool:
        """Whether a screen read as the shooting screen right after a MENU (or a closing Enter) inside a row a network
        decision opened ends the row: always, unless the row's own screen read as the shooting screen before any closing
        key went out ("suspect": Manage Paired Device's list did, 2026-11-13), when a frame reading as the shooting
        screen says nothing; then only when that frame is not the screen read so inside the row (screen.same_state) and
        the camera's own picture of the screen (osd_kind, as judged_screen asks it) reads as the shooting screen too. A
        picture that cannot be fetched or read keeps the row open."""
        suspect = inside.get("suspect")
        if suspect is None:
            return True
        try:
            if screen.same_state(self.screen, suspect):
                return False
        except Exception:                       # a screen that cannot be compared is no way out
            return False
        kind = self.osd_seen()
        self.run.log("shooting_inside_osd", frame=self.frame.path.name, row=inside["row"], osd=kind or None)
        return kind == "shooting"

    def _inside_after(self) -> None:
        """After a press or a read while a row a network decision opened is open: the row is left once a MENU (or an
        Enter on a named option) has gone out and the page it was opened from, or the shooting screen, is back
        (network_left), and its locks go; else the screen's text is judged, and one naming identity or credentials
        (safety.identity_screen: a pairing screen, a connecting notice naming an SSID), or a screen of no known kind,
        leaves MENU alone and no reader asked (camkit.vlm.HELD) until the row is left. A screen read as the shooting
        screen inside the row before any MENU or closing Enter has gone out is the row's own screen misread (only those
        keys leave a row): it is judged as no known kind (MENU alone, safety.inside_menu_only) and marked ("suspect"), so
        no later frame read as the shooting screen ends the row unless the camera's own picture says so (menu_closed).
        The link still judges every key on it as the shooting screen (decision 21: only MENU goes out there). The log
        names the frame, never the text."""
        inside = getattr(self, "network_open", None)
        if inside is None:
            return
        kind = getattr(self.screen, "kind", None)
        if kind == "shooting" and not self.closing_seen(inside) and inside.get("suspect") is None:
            inside["suspect"] = self.screen
            self.run.log("shooting_inside", frame=self.frame.path.name, row=inside["row"])
        if kind == "shooting" and inside.get("suspect") is not None:
            kind = "unknown"
        if self.network_left():
            self.network_open = self.address_open = self.identity_open = None
            if getattr(self, "blank", False):
                self.withhold(False)
            vlm.HELD = None
            self.run.log("network_row_left", frame=self.frame.path.name, row=inside["row"])
            return
        if getattr(self, "identity_open", None) is None:
            try:
                why = (safety.owner_menu_only(inside.get("class"), kind, text_of(self), inside["row"],
                                              inside.get("blank", False)) if inside.get("owner") else
                       safety.inside_menu_only(inside.get("class"), kind, text_of(self), inside["row"]))
            except Exception:                   # a screen whose text cannot be read is no permission
                why = "identity or credentials: the screen's text could not be read"
            if why:
                self.identity_open = self.frame.path.name
                vlm.HELD = "a screen naming identity or credentials is open"
                self.run.log("identity_screen", frame=self.frame.path.name)

    def judged_screen(self, key: str):
        """The screen a press or turn of `key` is judged on at the link: the screen read last, except a screen read as
        no known kind whose frame is dark (HDMI blanked; dark, not black, so one with something drawn on it is asked
        about too), which the camera's own picture of it decides (osd_kind): judged as the shooting screen when that reads as one (decision 21); Refused, for every key but MENU, when that
        picture cannot be read either, since a key pressed unseen may land on the shooting screen. Only ever adds a
        refusal: any other reading of the picture keeps the screen read last."""
        if safety.canonical_input(key) in safety.SHOOTING_FREE or getattr(self.screen, "kind", None) != "unknown" \
                or not dark(self.frame):
            return self.screen
        kind = self.osd_seen()
        self.run.log("black_frame_osd", key=key, frame=self.frame.path.name, osd=kind or None)
        if not kind:
            why = ("the frame is black and the camera's own picture of the screen could not be read: unseen, only MENU "
                   "goes out (docs/decisions/0021)")
            self.run.log("press_refused", key=key, frame=self.frame.path.name, why=why)
            raise safety.Refused(f"{key}: {why}")
        return playback_kind(self.link, "shooting") if kind == "shooting" else self.screen

    def dial(self, name: str, steps: int, on_shooting=frozenset()) -> screen.Screen:
        """A dial turned `steps` (drive.py's dial.NAME.STEPS), judged at the link on the screen read last as a press is
        (judged_screen; on the shooting screen a dial changes the live exposure: on_shooting must name the dial); the
        screen read again after it."""
        if getattr(self, "network_open", None) is not None:
            self.refuse(name, f"a row a network decision opened ({self.network_open['row']!r}) is open: no dial is "
                              "turned there, which could choose or commit an option (docs/decisions/0008)")
        self._fresh(name)
        self._recent(name)
        self.link.dial(name, steps, screen=self.judged_screen(name), on_shooting=on_shooting)
        time.sleep(0.6)
        return self.refresh("dial")

    def lit_by_reader(self, key: str, known=None) -> str:
        """The label of the lit row OCR read nothing in, inside a press: the reader's on this press's pass before, where
        the screen and its lit row are the ones it was read on (`known`); else the reader's now (unread_row), after
        which, the reader taking about a second, a frame by then older than STALE_S is looked at again (look_again):
        where it is no longer the screen the label was read on, the press is refused as a changed screen, nothing sent
        (safety.ScreenChanged, the fresh frame the camera's); else press judges it again from the top on the fresh frame
        (_Rejudge), every guard again, the label kept for that lit row (a gap found 2026-11-18: the key went out about
        a second after its frame, on whatever the camera showed by then)."""
        box = lit_box(self.frame.image)
        if known is not None and same_screen(self.screen, known["screen"]) and same_box(box, known["box"]):
            self.run.log("lit_row_label_kept", key=key, frame=self.frame.path.name)
            return known["label"]
        on, t = self.screen, getattr(self.frame, "t", None)
        label = self.unread_row(key)
        age = time.monotonic() - t if isinstance(t, (int, float)) and t > 0 else 0.0
        if age <= STALE_S:
            return label
        stale, fresh = look_again(getattr(self, "hdmi", None), on, key, getattr(self.link, "moved_at", None),
                                  read=self.reading)
        if fresh is None:
            self.refuse(key, stale)
        self.judge_fresh(fresh, key, changed=bool(stale))
        if stale:
            self.refuse(key, f"{stale} (the reader named the lit row on a frame {age:.1f} s old); read the screen again "
                             "and choose afresh", changed=True)
        self.run.log("press_judged_again", key=key, frame=fresh.path.name, age=round(age, 3))
        raise _Rejudge({"screen": self.screen, "box": box, "label": label})

    def unread_row(self, key: str) -> str:
        """The label of the lit row OCR read nothing in, as the vision reader reads it once (reader_label); Refused
        when it gives none, logged so the owner can open the row by hand. The label it gives is judged by the caller
        as an OCR reading is."""
        label, why_not = reader_label(self.frame.path)
        if label:
            # on a --network run the label is not logged: a bar can carry an identity value after it
            self.run.log("lit_row_by_reader", key=key, frame=self.frame.path.name,
                         label="(withheld)" if getattr(self, "network", None) or getattr(self, "owner", None) or getattr(self, "look", False) else label)
            return label
        self.run.log("press_refused", key=key, frame=self.frame.path.name, why=UNREAD, reader=why_not, by_hand=True)
        print(f"{key} refused on {self.frame.path.name}: {UNREAD} ({why_not}); if the row is one to open, open it on "
              f"the camera by hand", flush=True)
        raise safety.RowRefused(f"{key}: {UNREAD}")

    def read(self) -> screen.Screen:
        return self.screen

    def glance(self, tag: str) -> tuple:
        """(a frame grabbed now, not saved; the screen on it as this camera reads it), the camera's own frame and screen
        left as they are: a look a waiting loop takes many times (proving.nav.after_download: one every 0.4 s), whose
        deciding frame refresh(frame=) saves and makes the camera's."""
        f = self.hdmi.grab(tag, save=False)
        return f, self.reading(f)

    def refresh(self, tag: str, frame=None) -> screen.Screen:
        """Grab and read the screen now, without a press (after a download closed the menu); or take `frame`, one glance
        grabbed unsaved, saved now as the evidence it is (black while a row whose values are withheld is open)."""
        if frame is None:
            self.frame = self.hdmi.grab(tag)
        else:
            keep(frame, self.run.shot_path(tag), getattr(self.hdmi, "withheld", False))
            self.frame = frame
        self.screen = self.reading(self.frame)
        self.screen.frame_path = self.frame.path.name
        self.rest(f"{tag}-rest")
        self._seen = self._moves()
        self._inside_after()
        return self.screen

    def rest(self, tag: str, tries: int = 3) -> screen.Screen:
        """A menu page caught while it slides in or across reads as a menu with no focus (the rows panel between
        its two places): look again, longer, until it stops. A frame of the menu at rest is what every position
        check compares (2026-11-06: a mid-slide frame read as the group column, and the Right meant for it
        opened the row the cursor was on)."""
        for _ in range(tries):
            if not (self.screen.kind == "menu" and self.screen.focus is None):
                break
            self.frame, _ = self.hdmi.settle(self.frame, tag, expect_change=False, quiet=0.5, timeout=3.0)
            self.screen = self.reading(self.frame)
            self.screen.frame_path = self.frame.path.name
        return self.screen

    def cancel_to_menu(self, tries: int = 3):
        """After a STOP or an error: MENU (cleanup presses skip the STOP check) until a menu page, or the shooting screen
        or the playback view, where nothing is open to cancel (the run's end leaves the playback view:
        proving.nav.leave_playback)."""
        for _ in range(tries):
            if self.screen.kind in ("menu", "tiles", "shooting", "playback"):
                self._inside_after()
                return True
            t = time.monotonic()
            self.link.press("menu", cleanup=True)
            self.menu_went_out()
            f, _ = self.hdmi.settle(self.frame, "cancel", expect_change=True, sent_at=t)
            self.frame, self.screen = f, self.reading(f)
            self._seen = self._moves()
            self._inside_after()                # judged on the read right after this MENU (network_left spends it)
        self._inside_after()
        return self.screen.kind in ("menu", "tiles", "shooting", "playback")


def submenu_labels(cam, vlm_timeout: float = 25.0):
    """(page key, rows) for the submenu page on screen, read live before any Right on its rows.

    Each row: {"label", "never_open", "readings"}. OCR (fast, local) and vLLM (if it answers within
    vlm_timeout) both read the page; a row is never-open if EITHER reading flags it, and its label
    is the VLM's when there is one (OCR reads row icons as letters). A row neither could read gets
    an empty label and is not opened."""
    return _submenu_labels(cam, vlm_timeout)[:2]


def submenu_texts(lines, s) -> list:
    """The visible rows of the submenu page `s` as OCR read them (`lines`): each row's name, its value column left out."""
    return [ocr.text_in(lines, (55, top, 470, bottom)).strip() for top, bottom in s.rows[:s.count or 0]]


def _submenu_labels(cam, vlm_timeout: float):
    """submenu_labels' (page key, rows), and whether the reader answered."""
    f, s = cam.frame, cam.read()
    key = screen.rows_key(f.image)          # not just the page: scrolled lists keep their breadcrumb
    lines = ocr.read([f.path])[f.path]
    n = s.count or 0
    texts = submenu_texts(lines, s)
    vlm_labels, answered = [], False
    try:
        answer = ask_role("second", f.path.read_bytes(), PROMPTS["menu"], vlm_timeout)
        vlm_labels = [str(r.get("label") or "") for r in (answer.get("rows") or []) if isinstance(r, dict)]
        answered = True
    except Exception as e:
        # OCR alone; never-open is still checked on it, with its usual slips undone (safety.never_open)
        cam.run.log("reader_failed", frame=f.path.name, why=scrub(f"{type(e).__name__}: {e}"[:300]))
    rows = []
    for i in range(n):
        readings = [t for t in (texts[i] if i < len(texts) else "",
                                vlm_labels[i] if i < len(vlm_labels) else "") if t]
        why = next((w for w in (safety.never_open(t) for t in readings) if w), None)
        label = (vlm_labels[i] if i < len(vlm_labels) and vlm_labels[i] else (texts[i] if i < len(texts) else ""))
        rows.append({"label": label, "never_open": why, "readings": readings})
    return key, rows, answered


class PageLabels:
    """submenu_labels with each view of a submenu page read once: crawl_run's label reader, which camkit.crawl asks at
    every submenu row. A view is the page (screen.page_key) and its visible rows as OCR reads them on the frame, so the
    cursor's bar moving down the page keeps the view, while a page that scrolls instead of paging (Recog. Target) is a
    new view at each scroll; the reader (about 2.5 s a call) is asked once per view, OCR on every frame as before. A
    reading the reader did not answer is not kept (the next row asks again), nor is a view where OCR read a row as
    nothing (two views could share that key). Before 2026-11-18 the reader was asked at every row: the crawl's cache,
    keyed by screen.rows_key, was looked up only after the reading, and that key changes with the cursor (108 of 119
    submenu Downs, kit2_breadth_crawl). Each call is logged ("page_labels": frame, hit, calls, hits). What is checked
    at the press is not this: the never-open check at Right reads the live bar."""

    def __init__(self, vlm_timeout: float = 25.0):
        self.vlm_timeout, self.views, self.calls, self.hits = vlm_timeout, {}, 0, 0

    def __call__(self, cam):
        f, s = cam.frame, cam.read()
        texts = submenu_texts(ocr.read([f.path])[f.path], s)
        view = (screen.page_key(f.image), tuple(texts)) if texts and all(texts) else None
        got = self.views.get(view) if view is not None else None
        hit = got is not None
        if hit:
            self.hits += 1
        else:
            self.calls += 1
            key, rows, answered = _submenu_labels(cam, self.vlm_timeout)
            got = (key, rows)
            if view is not None and answered:
                self.views[view] = got
        log = getattr(getattr(cam, "run", None), "log", None)
        if log:
            log("page_labels", frame=f.path.name, hit=hit, calls=self.calls, hits=self.hits)
        return got


# The three below were card_actions.py's (now in kit/tools/) until 2026-11-04, when the scripts were grouped into
# kit/provers/ and kit/tools/: every prover and walker closes the camera with close(), so it lives with the camera.

def text_of(cam) -> str:
    """All the text OCR reads on the screen now."""
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], (0, 0, 640, 480)).strip()


# ---------------------------------------------------------------- MENU from the shooting screen: the one helper


def menu_check(cam, tag: str = "menu-check", clock=None, poll: float = MENU_POLL):
    """The screen after a MENU from the shooting screen that seemed not taken. Where that MENU's press watched for the
    menu already (LiveCamera.menu_watch, HDMI eyes: the screen read last is the frame its watch ended on), the screen
    read last, at once. Otherwise with HDMI eyes the frames are watched (LiveCamera.glance, unsaved) for up to MENU_LATE
    s and the first that reads as a menu page is taken at once (refresh(frame=)); where none comes, and with other eyes,
    a fresh frame after the full MENU_LATE s (refresh), which alone may say the MENU was not taken (2026-10-29: a second
    MENU on a menu that was only slow closed it, and the next Right, on the shooting screen, opened ISO). Logged
    ("menu_check": by "press" where the press's watch had looked, by "look" where this one did; seen, whether a menu page
    showed; waited, s). clock: the caller's time module (this module's by default)."""
    clock = clock or time
    log = getattr(getattr(cam, "run", None), "log", None) or (lambda *a, **k: None)
    watched = getattr(cam, "menu_watched", None)
    if watched is not None and getattr(cam, "frame", None) is watched:
        s = cam.read()
        log("menu_check", frame=watched.path.name, by="press", seen=s.kind in MENU_PAGES, waited=0)
        return s
    eyes = getattr(cam, "hdmi", None)
    start = clock.monotonic()
    s = None
    if getattr(eyes, "name", "") == "hdmi" and hasattr(cam, "glance"):
        while clock.monotonic() - start < MENU_LATE:
            clock.sleep(poll)
            f, seen = cam.glance(tag)
            if seen.kind in MENU_PAGES:
                s = cam.refresh(tag, frame=f)
                break
    else:
        clock.sleep(MENU_LATE)
    if s is None:
        s = cam.refresh(tag)
    log("menu_check", frame=getattr(getattr(getattr(cam, "frame", None), "path", None), "name", None), by="look",
        seen=s.kind in MENU_PAGES, waited=round(clock.monotonic() - start, 3))
    return s


def menu_from_shooting(cam, pressed: bool = False, shooting=None, clock=None, tries: int = 3) -> None:
    """MENU from the shooting screen, the one way every caller sends it: MENU (none where `pressed`, the caller having
    just sent it), and while the screen still reads as the shooting screen (`shooting`, a predicate on the screen, by
    default its kind), a fresh look first (menu_check: the press's own watch where it had one, LiveCamera.menu_watch;
    else at once on a menu page with HDMI eyes, else a fresh frame after MENU_LATE s), and only then MENU once more, `tries` times at most. Never a second MENU without that look just before
    it: a MENU the camera took late (its settle ended on the shooting screen's own redraw) opens the menu meanwhile, and
    a MENU then would close it, the next key landing on the shooting screen (kit2_pass2 250525-250527, 2026-11-18: a
    Left; 2026-10-29: a Right that opened ISO)."""
    shooting = shooting or (lambda s: s.kind == "shooting")
    if not pressed:
        cam.press("menu")
    for _ in range(tries):
        if not shooting(cam.read()):
            break
        if not shooting(menu_check(cam, "menu-check", clock=clock)):
            break
        cam.press("menu")


def press(cam, key: str, confirm=False, answer=None, **kw):
    """A press the camera may refuse for a moment while it reads the card (Select REC Folder
    refused Up 0.3 s after opening and took MENU 1.6 s later, 2026-10-29). kw: LiveCamera.press's (on_shooting).
    confirm: the caller judged this press with the confirmation check lifted (the owner route's step or armed press;
    True, or the words naming it); answer: a consent named for this press's screen (LiveCamera.answer_once). Either is
    given to the first try, and to a later one only when the screen, read again, is the state the caller judged: a
    retry never answers a screen nobody judged. Only the camera's own refusal ("button not accepted":
    camkit.link.CameraRefused, nothing done) is tried again; a button left held ("button_held": it went down and may
    have acted), no reply or anything else raises at once, and nothing is pressed again. A press refused because the
    screen changed since the caller read it (safety.ScreenChanged) is tried once more, and only where the screen read
    afresh is again the state the caller judged (a popup gone, a picture that caught up and back): the caller chose the
    press on that state; else the refusal stands."""
    judged = getattr(cam, "screen", None)
    changed = None
    for attempt in range(6):
        try:
            if attempt:
                cam.refresh("retry")            # the screen the retry is judged on, read afresh
            same = attempt == 0 or same_screen(getattr(cam, "screen", None), judged)
            if changed is not None and not same:
                raise changed                   # still not the state the caller judged: no press on it
            if confirm and same:
                cam.confirm_once = confirm
            if answer and same:
                cam.answer_once = answer
            return cam.press(key, **kw)
        except safety.ScreenChanged as e:
            if changed is not None or attempt == 5:
                raise
            changed = e
        except CameraRefused:
            if attempt == 5:
                raise
            time.sleep(1.0)


def withheld_on(cam, text) -> str:
    """`text` (an error's) as a print shows it on `cam`'s run: on a --network or --owner run (LiveCamera.network,
    LiveCamera.owner) its quoted texts withheld, as the run's first error line and LiveCamera.refuse withhold them: a
    command's quoted argument can be the OSD frame's full path, with the home folder in it (2026-11-14)."""
    return safety.quoted_withheld(text) if getattr(cam, "network", None) or getattr(cam, "owner", None) or getattr(cam, "look", False) else str(text)


def close(cam, link):
    """Back to the shooting screen. The camera can refuse a button for a moment ("button not
    accepted" right after Select REC Folder opened, while it read the card, 2026-10-29): wait and
    try again; never return with a screen open, since disconnecting then is not allowed. The camera's playback view
    (LiveCamera.reading) holds nothing open either: close stops there, with MENU alone sent, as it did while that view
    read as the shooting screen, and the run's end leaves it (proving.nav.leave_playback, before its download). On a
    link in the SDK's network-error state every command, its MENU among them, waits for the recovery at the link
    (Link.call, _net_wait), as every other command of the run does."""
    for _ in range(8):
        try:
            cam.cancel_to_menu()
            if cam.read().kind in ("menu", "tiles", "submenu"):
                link.press("menu", cleanup=True)
                getattr(cam, "menu_went_out", lambda: None)()       # a network row's lock may end on the shooting screen
                time.sleep(1.0)
            if cam.refresh("closing").kind in ("shooting", "playback"):
                return
        except LinkError as e:
            print(f"closing: {withheld_on(cam, e)}; trying again", flush=True)
        time.sleep(1.5)
        try:
            cam.refresh("closing")              # the look the next try starts from: one that fails is one more try
        except LinkError as e:
            print(f"closing: {withheld_on(cam, e)}; trying again", flush=True)
    raise SystemExit("could not get back to the shooting screen: please close it on the camera by hand")
