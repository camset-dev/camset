"""The one step after OK: what the camera did with a choice, read off the screen the OK left (after_ok), lifted out of
kit/prove_run.py's prove_row on 2026-11-19 (the engineering review of 2026-11-18, finding 10: five provers wrote
"applied": true whatever the camera answered, two took any notice for a refusal, and "applied" was decided five ways).

    got = after_ok(cam, "Drive Mode > Cont. Bracket", label="1.0 EV 5 Img.")
    rec = {..., "notice": got.notice, "applied": got.applied}

The outcomes (Outcome.kind), in the order the screen is judged:
    refused         a notice that refuses the choice ("not available as follows <blocker>", "invalid"), closed with
                    MENU, never OK; the value stayed as it was, and the line says "applied": false with the notice
    notice-closed   any other notice (an information notice after the choice applied: Sync Terminal's "Enters the
                    state with Flash Effect dur Sht. applied"), closed with MENU (which on the a1 II closes the menu too)
    menu-closed     the shooting screen: the choice closed the menu (Focus Area = Wide, Shoot Mode)
    back-on-page    the menu page the row is on, where the caller says how to know it (`page`): a choice that rebuilds
                    the menu (XAVC HS 8K's Rec Frame Rate)
    info-ok         an information screen not the row (one of no known kind, or a table with buttons: Exposure Ctrl
                    Type's), where the caller takes them (`info`), left by proving.screens.info_notice_ok's rules: MENU
                    first, its OK only where the camera refuses MENU and OK is its only button, or where the screen's
                    kind takes an Enter; a table must be back on the row after it
    applied         back on the row (`back`; by default any menu page)
Every outcome but "refused" is an applied choice: the download after it shows what applied. A screen that asks a
question raises Asked (a Failed), nothing answered: the caller cancels it with MENU. Any other screen raises Failed,
nothing pressed. The only presses are MENU on a notice and what info_notice_ok presses on an information screen: no
key the guards would not send (camkit.live judges each press), and the confirmation check before OK stays the caller's.
"""
import re
from typing import NamedTuple

from camkit import ocr, safety
from camkit.live import MENU_PAGES

from . import screens
from .base import Failed

APPLIED, REFUSED, NOTICE_CLOSED, MENU_CLOSED, BACK_ON_PAGE, INFO_OK = (
    "applied", "refused", "notice-closed", "menu-closed", "back-on-page", "info-ok")
# a notice after OK that refuses the choice, as prove_row has told one since 2026-10-29 (a caller may give its own words)
REFUSED_WORDS = re.compile(r"not available|invalid", re.I)
MENU_CLOSED_TEXT = "the menu closed after OK"
BACK_ON_PAGE_TEXT = "the camera went back to the menu page after OK"
WHOLE = (0, 0, 640, 480)


class Asked(Failed):
    """A screen after OK that asks a question (safety.confirmation): `why` and the `frame` it was read on."""

    def __init__(self, message: str, why: str, frame: str):
        super().__init__(message)
        self.why, self.frame = why, frame


class Outcome(NamedTuple):
    """What the camera did with the choice (kind: one of the module's outcomes) and the notice a proof line keeps:
    {"text", "frame"} (a network row's: what `withhold` keeps, and the frame; an information screen's: info_notice_ok's
    {"text", "frame", "left_by"}), None where the screen went straight back to the row."""
    kind: str
    notice: dict | None = None

    @property
    def refused(self) -> bool:
        return self.kind == REFUSED

    @property
    def applied(self) -> bool:
        return self.kind != REFUSED


def on_menu_page(cam) -> bool:
    """The screen on show is a menu page (camkit.live.MENU_PAGES): the row's, for a caller that keeps no row place."""
    return cam.read().kind in MENU_PAGES


def _say(message: str) -> None:
    print(message, flush=True)


def after_ok(cam, name: str, *, back=None, page=None, info: bool = True, label=None, read=None, withhold=None,
             refusal=REFUSED_WORDS, say=_say) -> Outcome:
    """The outcome of the OK just pressed on `cam` (the module's), for the row `name` (and the option `label`, in the
    messages). back(): whether the screen is back on the row (prove_row: the place it had before Right), by default any
    menu page (on_menu_page); page(): whether it is back on the menu page the row is on, judged only on a menu screen
    and never where None; info: whether an information screen not the row (no known kind, a table) is left by
    info_notice_ok's rules, else it fails (a prover whose own screen reads as no known kind gives False); read(cam): the
    notice's whole text (orient_run's portrait screens, pass 3's notice_text), by default OCR's reading of the whole
    frame; withhold(lines): a network row's: what is kept of the notice instead of its text (safety.kept_screen, on
    OCR's lines), nothing of it said; refusal: the words that make a notice a refusal; say: where the step's lines go
    (prove_row's tell; None says nothing)."""
    say = say or (lambda message: None)
    on = f" on {label!r}" if label is not None else ""
    back = back or (lambda: on_menu_page(cam))
    s = cam.read()
    if s.kind == "notice":
        frame = cam.frame.path.name
        lines = screens.frame_lines(cam) if read is None or withhold is not None else None
        text = read(cam) if read is not None else ocr.text_in(lines, WHOLE)
        why = safety.confirmation(text)
        if why:
            raise Asked(f"{name}: after OK{on} a confirmation came up ({why}; {frame})", why, frame)
        refused = bool(refusal.search(text))
        if withhold is not None:
            notice = {**withhold(lines), "frame": frame}
        else:
            notice = {"text": text, "frame": frame}
            say(f"   {'refused' if refused else 'notice after OK'}: {text[:90]!r}")
        cam.press("menu")
        return Outcome(REFUSED if refused else NOTICE_CLOSED, notice)
    if s.kind == "shooting":
        say("   the menu closed after OK")
        return Outcome(MENU_CLOSED, {"text": MENU_CLOSED_TEXT, "frame": cam.frame.path.name})
    if s.kind == "menu" and page is not None and page():
        say("   back on the menu page after OK")
        return Outcome(BACK_ON_PAGE, {"text": BACK_ON_PAGE_TEXT, "frame": cam.frame.path.name})
    if s.kind == "unknown" and info and not back():
        # an information screen without a notice's frame lines, "Don't show this again." over its OK (Framing
        # Stabilizer = On: Center, Movie mode, 2026-10-30), never ticking the box
        return Outcome(INFO_OK, screens.info_notice_ok(cam, name))
    if s.kind == "table" and info and not back():
        # an information screen with buttons (Exposure Ctrl Type = Flexible Exp. Mode: "Changes keys assigned to suit
        # this mode", 2026-11-07): its OK applies the choice
        notice = screens.info_notice_ok(cam, name, kinds=("table",))
        if not back():
            raise Failed(f"{name}: after the information's OK the screen is {cam.read().kind} "
                         f"({cam.frame.path.name}), not the row")
        return Outcome(INFO_OK, notice)
    if not back():
        raise Failed(f"{name}: after OK{on} the screen is {s.kind} ({cam.frame.path.name}), not the row")
    return Outcome(APPLIED)
