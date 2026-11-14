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
press is refused, since the never-open check cannot judge a row it cannot read (2026-11-08).

The screen read last goes with every press and dial to the link, whose guards judge C4 on it (decision 7) and every key
but MENU on the shooting screen (decision 21: refused there unless the caller names the key for that press,
on_shooting). A screen read as no known kind whose frame is black (HDMI blanked: Auto Framing On in Movie mode) is
asked of the camera's own picture first (judged_screen), and judged as the shooting screen when that reads as one; when
that picture cannot be read, no key but MENU goes. A shooting screen that is drawn but read as another kind (a DISP
mode that draws no battery) is not caught: the kit presses on unknown screens on purpose (the memory slots read as one).
The screen judged is never one the camera has left behind this camera's back: the link counts what can move it (a
download, an upload, any press or dial), and when that count has moved since the last read, the screen is grabbed and
read afresh before the press is judged (_fresh: a refresh, never a refusal).
Enter on a confirmation is each caller's check (safety.confirmation, as drive.py's press_decision and the provers make
it before their OK): the choke point does not make it, since what a confirmation looks like differs by screen and no
one rule could be proved on every prover without the camera.

The orange cursor is found as a bar first (lit_box). A dialog or table that lights its item without one (the White
Balance chooser's orange text, a two-slot table's narrow cell) is read from the largest orange region instead, on those
screens alone: on a menu page a lit row is always a bar, and its orange texts are values on unlit rows (2026-11-08)."""
import atexit
import contextlib
import os
import shutil
import tempfile
import time
from pathlib import Path

import numpy as np

from . import ocr, safety, screen, vlm
from .frames import keep
from .link import LinkError
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
                 readings=None) -> str:
    """Why a press may not open the lit row, or "": the row's text is never-open, and no name the run was given
    lifts it (drive.py --allow lifts what it may; never what safety.never_lifted names: the cards, Initialize, Reset
    Network Set., credentials, and the camera's identity, a connection or its region, decision 8). A Wi-Fi or Bluetooth
    setting or an address screen (safety.NETWORK, or its words in a row of another reason) is lifted only by a dated
    owner decision naming the row (`network`, safety.network_decided's rows, for a run given --network:
    safety.network_lifted, its label, or a reading of it another reader read as the label (`readings`), followed by
    nothing or one of its `values`, an address screen only with `screens`), never by the substring match of
    `may_open`."""
    why = safety.never_open(lit)
    if not why:
        return ""
    if network and safety.network_lifted(lit, network, screens, values, readings):
        return ""                       # a network decision names it: a Wi-Fi or Bluetooth setting, an identity row
    if why.startswith(safety.NETWORK + ":"):
        return (f"the lit row {lit.strip()!r} is never opened ({why}; only a dated owner decision naming the row opens "
                "it, with --network)")
    # a name and the reading compared as the guards fold them: "Pre-AF" names a "Pre‑AF" read with a no-break hyphen
    seen = safety.clean_label(safety.fold(lit))
    named = any(safety.clean_label(safety.fold(m)) and safety.clean_label(safety.fold(m)) in seen for m in may_open)
    if named and not safety.never_lifted(lit) and not safety.network_words(lit):
        return ""
    return f"the lit row {lit.strip()!r} is never opened ({why})"


OK_LATE = 4.0           # how long OK gets to show when the camera is busy applying what it chose (seconds)
# a frame this dark on average shows no screen to read: HDMI blanked (camkit.session.osd_shooting's level)
BLACK = 6.0


def black(frame) -> bool:
    """The frame shows nothing to read: its picture this dark on average (BLACK). A frame without a picture is not."""
    image = getattr(frame, "image", None)
    return isinstance(image, np.ndarray) and image.size > 0 and float(image.mean()) <= BLACK


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


class LiveCamera:
    def __init__(self, link, hdmi, run, may_open=(), network=(), screens: bool = False, options=None, values=None,
                 readings=None, owner=None):
        self.link, self.hdmi, self.run = link, hdmi, run
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
        self.screens = bool(screens)
        self.options = dict(options or {})
        self.values = dict(values or {})
        self.readings = dict(readings or {})
        self.network_open = self.address_open = self.identity_open = None
        # one row lifted for one press (kit/provers/pp_reset_run.py's Reset): a predicate (frame, lit) -> bool, set
        # by the caller for its next press and used up by that press; None (unset) changes nothing
        self.may_open_exact = None
        self.frame = hdmi.grab("live-start")
        self.screen = screen.read(self.frame)
        self.screen.frame_path = self.frame.path.name
        self.presses = 0
        self._seen = self._moves()      # the link's count of screen-moving commands at the screen's last read

    def _moves(self) -> int:
        """The link's count of the commands sent that can move the screen (camkit.link.MOVES: a download, an upload,
        any press or dial, this camera's own among them); 0 for a link that keeps none."""
        return getattr(self.link, "moves", 0)

    def _fresh(self, key: str):
        """The screen read afresh when something moved it since the last read without this camera seeing it (a
        download or an upload, a press sent straight through the link, proving.nav.to_shooting's own MENU presses): the
        link's count moved past the one kept at that read. A refresh, never a refusal; MENU needs none, since it is
        judged on no screen and the read after it is fresh."""
        if safety.canonical_input(key) in safety.SHOOTING_FREE or self._moves() == getattr(self, "_seen", self._moves()):
            return
        self.run.log("screen_stale", key=key, frame=self.frame.path.name, moves=self._moves())
        self.refresh("stale")

    def press(self, key: str, allow=frozenset(), hold_ms=60, on_shooting=frozenset()):
        """One press, read once it settles. allow: the guarded buttons named (safety.GUARDED_INPUTS); on_shooting: the
        keys named for this press on the shooting screen, where a key does what the body makes of it (decision 21):
        a caller names a key there only where pressing it there is the point."""
        exact = getattr(self, "may_open_exact", None)
        if exact is not None:
            self.may_open_exact = None      # one press only, whatever it is
        permit = getattr(self, "permit", None)
        self.permit = None                  # drive.py's word for one owner press: used up by this press, whatever it is
        arming = self.inside_refused(key, permit)       # inside a network row: look only, or MENU alone
        # a MENU, or an Enter inside_refused let through (an option the decision names), may close the row once it has
        # gone out: only then can the lock end (_inside_after)
        closes = getattr(self, "network_open", None) is not None and safety.canonical_input(key) in CLOSES
        self._fresh(key)                    # the screen the press is judged on is never one the camera has left
        # the never-open check judges the key as the guards read it (" right" and "Right" are Right), so a padded or
        # look-alike spelling never skips it; the link then refuses any spelling that is not the key's own name
        network, screens = getattr(self, "network", ()), getattr(self, "screens", False)
        values, opened, address, cls = getattr(self, "values", {}), None, False, None
        readings = getattr(self, "readings", {})
        owner, owner_row = getattr(self, "owner", None) or {}, None
        if safety.canonical_input(key) in OPENS and self.screen.kind in ROW_SCREENS:
            lit = lit_text(self.frame.image, self.frame.path)
            if not lit.strip() and lit_box(self.frame.image) is not None:
                lit = self.unread_row(key)          # a bar OCR read nothing in: the reader names it, or no press
            why = open_refused(lit, self.may_open, network, screens, values, readings)
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
                self.refuse(key, why)
            if owner_row is not None:
                opened, cls = owner_row, owner[owner_row].get("class")
                address = cls == safety.LIFT_ADDRESS
            elif network and getattr(self, "network_open", None) is None:
                opened = safety.network_lifted_row(lit, network, screens, values, readings)
                cls = safety.lift_class(lit) if opened else None
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
        judged = self.judged_screen(key)
        t = time.monotonic()
        before = self.screen
        if arming:
            self.owner_done = True          # an armed press, once: from here only MENU, whatever answers it
            self.run.log("armed_press", key=key, frame=self.frame.path.name, row=arming[0], what=arming[1])
        # the safety allow-list, the STOP check, C4's screen check and the shooting screen's live there: the screen
        # read last goes with it
        self.handed = getattr(self, "handed", 0) + 1
        self.link.press(key, hold_ms, allow=allow, screen=judged, on_shooting=on_shooting)
        if closes:
            self.menu_went_out()
        if owner_row is not None:
            info = owner[owner_row]
            blank = cls in safety.BLANKED and not info.get("logged")
            self.owner_opened = True
            self.network_open = {"row": owner_row, "address": address, "class": cls, "frame": self.frame.path.name,
                                 "from": before, "closing": False, "menus": getattr(self.link, "menus", None),
                                 "owner": True, "blank": blank, "logged": bool(info.get("logged"))}
            self.run.log("owner_row_opened", key=key, frame=self.frame.path.name, row=owner_row, lifted_from=cls,
                         blank=blank)
            if blank or address or cls == safety.LIFT_SERIAL:
                self.identity_open = self.frame.path.name       # MENU alone from its opening
            if blank:
                self.withhold(True)             # before the frame it opened is settled and saved
                vlm.HELD = "a row whose values are withheld is open"
            opened = None
        if opened is not None:
            # a row a network decision opens: from here, whatever its screen reads as, look only (inside_refused), and
            # on an address screen MENU alone, no reader asked, until a MENU (or an Enter on a named option) has gone
            # out and the page it was opened from, or the shooting screen, is back (_inside_after). "menus": the
            # link's count of MENU presses now, so that a MENU sent past this camera (a cleanup press) counts too
            self.network_open = {"row": opened, "address": address, "class": cls, "frame": self.frame.path.name,
                                 "from": before, "closing": False, "menus": getattr(self.link, "menus", None)}
            self.run.log("network_row_opened", key=key, frame=self.frame.path.name, row=opened, lifted_from=cls)
            if address:
                self.address_open = self.frame.path.name
                vlm.HELD = "an address screen is open"
                self.run.log("address_screen_opened", key=key, frame=self.frame.path.name)
        # every press expects a change: a press that seems ignored gets a full second before it counts
        # as "nothing happened" (Picture Profile: a Down showed no change within 0.5 s, 2026-10-28)
        f, moved = self.hdmi.settle(self.frame, key, expect_change=True, sent_at=t)
        self.frame, self.screen = f, screen.read(f)
        self.rest(f"{key}-rest")
        f = self.frame
        if screen.same_state(self.screen, before):
            # looks like nothing happened: look again a little later. Live view behind a dialog that
            # previews each option (Picture Profile) keeps changing, which can end the settle before
            # the cursor has moved (2026-10-28). OK that applies a setting can hold the OSD image for
            # about 3 s while the camera applies it (Drive Mode's self-timer over the OSD, 2026-11-06: the
            # record had changed and the row page was back, the picture of it came 3.25 s after the press,
            # where HDMI showed it in 0.2 s): OK is given OK_LATE in all, a look every half second
            end = time.monotonic() + (OK_LATE if key == "enter" else 0.5)
            while True:
                time.sleep(0.5)
                f2 = self.hdmi.grab(f"{key}-late", save=False)
                s2 = screen.read(f2)
                if not screen.same_state(s2, before):
                    keep(f2, self.run.shot_path(f"{key}-late"), getattr(self, "blank", False))
                    f, self.frame, self.screen = f2, f2, s2
                    break
                if time.monotonic() >= end:
                    break
        self.screen.frame_path = f.path.name          # evidence: which saved frame this screen is
        self.presses += 1
        self._seen = self._moves()
        self.run.log("press", key=key, frame=f.path.name, screen=self.screen.kind, moved=moved,
                     timing=self.hdmi.timing)
        self._inside_after()

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
            why = safety.look_refused(key, lit, inside["row"], getattr(self, "options", {}).get(inside["row"]))
        if why:
            self.refuse(key, why)

    def refuse(self, key: str, why: str) -> None:
        """A press refused: logged in the run's events.jsonl and raised (safety.Refused). On a --network run (network
        given) the reason's quoted texts are withheld in both, since a row's bar can carry an identity value (a device's
        name, an SSID, an address): safety.quoted_withheld."""
        said = safety.quoted_withheld(why) if getattr(self, "network", None) or getattr(self, "owner", None) else why
        self.run.log("press_refused", key=key, frame=self.frame.path.name, why=said)
        raise safety.Refused(f"{key}: {said}")

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
        # (safety.bar_on_row: "LANIP Address Setting" still reads so after MENU)
        return safety.bar_on_row(lit, inside["row"], getattr(self, "readings", {}))

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
                       safety.inside_menu_only(inside.get("class"), kind, text_of(self)))
            except Exception:                   # a screen whose text cannot be read is no permission
                why = "identity or credentials: the screen's text could not be read"
            if why:
                self.identity_open = self.frame.path.name
                vlm.HELD = "a screen naming identity or credentials is open"
                self.run.log("identity_screen", frame=self.frame.path.name)

    def judged_screen(self, key: str):
        """The screen a press or turn of `key` is judged on at the link: the screen read last, except a screen read as
        no known kind whose frame is black (HDMI blanked), which the camera's own picture of it decides (osd_kind):
        judged as the shooting screen when that reads as one (decision 21); Refused, for every key but MENU, when that
        picture cannot be read either, since a key pressed unseen may land on the shooting screen. Only ever adds a
        refusal: any other reading of the picture keeps the screen read last."""
        if safety.canonical_input(key) in safety.SHOOTING_FREE or getattr(self.screen, "kind", None) != "unknown" \
                or not black(self.frame):
            return self.screen
        kind = self.osd_seen()
        self.run.log("black_frame_osd", key=key, frame=self.frame.path.name, osd=kind or None)
        if not kind:
            why = ("the frame is black and the camera's own picture of the screen could not be read: unseen, only MENU "
                   "goes out (docs/decisions/0021)")
            self.run.log("press_refused", key=key, frame=self.frame.path.name, why=why)
            raise safety.Refused(f"{key}: {why}")
        return "shooting" if kind == "shooting" else self.screen

    def dial(self, name: str, steps: int, on_shooting=frozenset()) -> screen.Screen:
        """A dial turned `steps` (drive.py's dial.NAME.STEPS), judged at the link on the screen read last as a press is
        (judged_screen; on the shooting screen a dial changes the live exposure: on_shooting must name the dial); the
        screen read again after it."""
        if getattr(self, "network_open", None) is not None:
            self.refuse(name, f"a row a network decision opened ({self.network_open['row']!r}) is open: no dial is "
                              "turned there, which could choose or commit an option (docs/decisions/0008)")
        self._fresh(name)
        self.link.dial(name, steps, screen=self.judged_screen(name), on_shooting=on_shooting)
        time.sleep(0.6)
        return self.refresh("dial")

    def unread_row(self, key: str) -> str:
        """The label of the lit row OCR read nothing in, as the vision reader reads it once (reader_label); Refused
        when it gives none, logged so the owner can open the row by hand. The label it gives is judged by the caller
        as an OCR reading is."""
        label, why_not = reader_label(self.frame.path)
        if label:
            # on a --network run the label is not logged: a bar can carry an identity value after it
            self.run.log("lit_row_by_reader", key=key, frame=self.frame.path.name,
                         label="(withheld)" if getattr(self, "network", None) or getattr(self, "owner", None) else label)
            return label
        self.run.log("press_refused", key=key, frame=self.frame.path.name, why=UNREAD, reader=why_not, by_hand=True)
        print(f"{key} refused on {self.frame.path.name}: {UNREAD} ({why_not}); if the row is one to open, open it on "
              f"the camera by hand", flush=True)
        raise safety.Refused(f"{key}: {UNREAD}")

    def read(self) -> screen.Screen:
        return self.screen

    def refresh(self, tag: str) -> screen.Screen:
        """Grab and read the screen now, without a press (after a download closed the menu)."""
        self.frame = self.hdmi.grab(tag)
        self.screen = screen.read(self.frame)
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
            self.screen = screen.read(self.frame)
            self.screen.frame_path = self.frame.path.name
        return self.screen

    def cancel_to_menu(self, tries: int = 3):
        """After a STOP or an error: MENU (cleanup presses skip the STOP check) until a menu page."""
        for _ in range(tries):
            if self.screen.kind in ("menu", "tiles", "shooting"):
                self._inside_after()
                return True
            t = time.monotonic()
            self.link.press("menu", cleanup=True)
            self.menu_went_out()
            f, _ = self.hdmi.settle(self.frame, "cancel", expect_change=True, sent_at=t)
            self.frame, self.screen = f, screen.read(f)
            self._seen = self._moves()
            self._inside_after()                # judged on the read right after this MENU (network_left spends it)
        self._inside_after()
        return self.screen.kind in ("menu", "tiles", "shooting")


def submenu_labels(cam, vlm_timeout: float = 25.0):
    """(page key, rows) for the submenu page on screen, read live before any Right on its rows.

    Each row: {"label", "never_open", "readings"}. OCR (fast, local) and vLLM (if it answers within
    vlm_timeout) both read the page; a row is never-open if EITHER reading flags it, and its label
    is the VLM's when there is one (OCR reads row icons as letters). A row neither could read gets
    an empty label and is not opened."""
    f, s = cam.frame, cam.read()
    key = screen.rows_key(f.image)          # not just the page: scrolled lists keep their breadcrumb
    lines = ocr.read([f.path])[f.path]
    n = s.count or 0
    texts = []
    for top, bottom in s.rows[:n]:
        texts.append(ocr.text_in(lines, (55, top, 470, bottom)).strip())
    vlm_labels = []
    try:
        answer = ask_role("second", f.path.read_bytes(), PROMPTS["menu"], vlm_timeout)
        vlm_labels = [str(r.get("label") or "") for r in (answer.get("rows") or []) if isinstance(r, dict)]
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
    return key, rows


# The three below were card_actions.py's (now in kit/tools/) until 2026-11-04, when the scripts were grouped into
# kit/provers/ and kit/tools/: every prover and walker closes the camera with close(), so it lives with the camera.

def text_of(cam) -> str:
    """All the text OCR reads on the screen now."""
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], (0, 0, 640, 480)).strip()


def press(cam, key: str, **kw):
    """A press the camera may refuse for a moment while it reads the card (Select REC Folder
    refused Up 0.3 s after opening and took MENU 1.6 s later, 2026-10-29). kw: LiveCamera.press's (on_shooting)."""
    for attempt in range(6):
        try:
            return cam.press(key, **kw)
        except LinkError as e:
            if "not accepted" not in str(e) or attempt == 5:
                raise
            time.sleep(1.0)


def close(cam, link):
    """Back to the shooting screen. The camera can refuse a button for a moment ("button not
    accepted" right after Select REC Folder opened, while it read the card, 2026-10-29): wait and
    try again; never return with a screen open, since disconnecting then is not allowed."""
    for _ in range(8):
        try:
            cam.cancel_to_menu()
            if cam.read().kind in ("menu", "tiles", "submenu"):
                link.press("menu", cleanup=True)
                getattr(cam, "menu_went_out", lambda: None)()       # a network row's lock may end on the shooting screen
                time.sleep(1.0)
            if cam.refresh("closing").kind == "shooting":
                return
        except LinkError as e:
            print(f"closing: {e}; trying again", flush=True)
        time.sleep(1.5)
        cam.refresh("closing")
    raise SystemExit("could not get back to the shooting screen: please close it on the camera by hand")
