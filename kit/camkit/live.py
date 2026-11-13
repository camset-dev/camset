"""The walkers' camera interface (press / read) on the real camera: each press goes over the link
and the screen is read once it settles over HDMI. Every settled frame is saved and every press is
logged in the run's events.jsonl. A STOP file raises link.StopRequested at the next press.

LiveCamera.press is the one way a walker, a prover or drive.py presses, so the row check lives there too: a press
that opens the lit row (Right, Enter, the multi-selector's right or centre, however the key is spelled) on a menu or
submenu page is refused when the lit row's text is on the never-open list (safety.never_open), unless the run named
that row as one it may open (may_open: drive.py --allow, a dated owner decision) and the reason is one such a name can
lift. It fails closed as drive.py does: when an orange bar is drawn but OCR reads no text in it, the vision reader is
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
import contextlib
import os
import tempfile
import time
from pathlib import Path

import numpy as np

from . import ocr, safety, screen
from .link import LinkError
from .vlm import PROMPTS, ask_role, log_to, scrub


# Presses that open the row under the cursor, and the screens whose lit bar is a row
OPENS = frozenset({"right", "enter", "ms_right", "ms_enter"})
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


def open_refused(lit: str, may_open=frozenset()) -> str:
    """Why a press may not open the lit row, or "": the row's text is never-open, and no name the run was given
    lifts it (drive.py --allow lifts what it may; never what safety.never_lifted names: the cards, Initialize, Reset
    Network Set., credentials, and the camera's identity, a connection or its region, decision 8)."""
    why = safety.never_open(lit)
    if not why:
        return ""
    # a name and the reading compared as the guards fold them: "Pre-AF" names a "Pre‑AF" read with a no-break hyphen
    seen = safety.clean_label(safety.fold(lit))
    named = any(safety.clean_label(safety.fold(m)) and safety.clean_label(safety.fold(m)) in seen for m in may_open)
    if named and not safety.never_lifted(lit):
        return ""
    return f"the lit row {lit.strip()!r} is never opened ({why})"


OK_LATE = 4.0           # how long OK gets to show when the camera is busy applying what it chose (seconds)
# a frame this dark on average shows no screen to read: HDMI blanked (camkit.session.osd_shooting's level)
BLACK = 6.0


def black(frame) -> bool:
    """The frame shows nothing to read: its picture this dark on average (BLACK). A frame without a picture is not."""
    image = getattr(frame, "image", None)
    return isinstance(image, np.ndarray) and image.size > 0 and float(image.mean()) <= BLACK


def osd_kind(link) -> str:
    """The kind of screen the camera's own picture of it reads as (the SDK's OSD image, fetched as
    camkit.session.osd_shooting fetches it, into a file of this process's own, removed after), or "" when it cannot be
    fetched or read."""
    from .frames import load
    path = Path(tempfile.gettempdir()) / f"camkit_osd_{os.getpid()}_press.png"
    try:
        return screen.read(load(link.osd(path))).kind or ""
    except Exception:
        return ""
    finally:
        with contextlib.suppress(OSError):
            path.unlink()


class LiveCamera:
    def __init__(self, link, hdmi, run, may_open=()):
        self.link, self.hdmi, self.run = link, hdmi, run
        log_to(run)                     # a reader that fails during the run is logged in its events.jsonl (camkit.vlm)
        self.may_open = frozenset(may_open)            # never-open rows this run was told it may open
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
        self._fresh(key)                    # the screen the press is judged on is never one the camera has left
        # the never-open check judges the key as the guards read it (" right" and "Right" are Right), so a padded or
        # look-alike spelling never skips it; the link then refuses any spelling that is not the key's own name
        if safety.canonical_input(key) in OPENS and self.screen.kind in ROW_SCREENS:
            lit = lit_text(self.frame.image, self.frame.path)
            if not lit.strip() and lit_box(self.frame.image) is not None:
                lit = self.unread_row(key)          # a bar OCR read nothing in: the reader names it, or no press
            why = open_refused(lit, self.may_open)
            if why and exact is not None and not safety.never_lifted(lit) and exact(self.frame, lit):
                self.run.log("press_lifted_exact", key=key, frame=self.frame.path.name, lit=lit)
                why = ""
            if why:
                self.run.log("press_refused", key=key, frame=self.frame.path.name, why=why)
                raise safety.Refused(f"{key}: {why}")
        judged = self.judged_screen(key)
        t = time.monotonic()
        before = self.screen
        # the safety allow-list, the STOP check, C4's screen check and the shooting screen's live there: the screen
        # read last goes with it
        self.link.press(key, hold_ms, allow=allow, screen=judged, on_shooting=on_shooting)
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
                    f2.save(self.run.shot_path(f"{key}-late"))
                    f, self.frame, self.screen = f2, f2, s2
                    break
                if time.monotonic() >= end:
                    break
        self.screen.frame_path = f.path.name          # evidence: which saved frame this screen is
        self.presses += 1
        self._seen = self._moves()
        self.run.log("press", key=key, frame=f.path.name, screen=self.screen.kind, moved=moved,
                     timing=self.hdmi.timing)

    def judged_screen(self, key: str):
        """The screen a press or turn of `key` is judged on at the link: the screen read last, except a screen read as
        no known kind whose frame is black (HDMI blanked), which the camera's own picture of it decides (osd_kind):
        judged as the shooting screen when that reads as one (decision 21); Refused, for every key but MENU, when that
        picture cannot be read either, since a key pressed unseen may land on the shooting screen. Only ever adds a
        refusal: any other reading of the picture keeps the screen read last."""
        if safety.canonical_input(key) in safety.SHOOTING_FREE or getattr(self.screen, "kind", None) != "unknown" \
                or not black(self.frame):
            return self.screen
        kind = osd_kind(self.link)
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
            self.run.log("lit_row_by_reader", key=key, frame=self.frame.path.name, label=label)
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
                return True
            t = time.monotonic()
            self.link.press("menu", cleanup=True)
            f, _ = self.hdmi.settle(self.frame, "cancel", expect_change=True, sent_at=t)
            self.frame, self.screen = f, screen.read(f)
            self._seen = self._moves()
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
                time.sleep(1.0)
            if cam.refresh("closing").kind == "shooting":
                return
        except LinkError as e:
            print(f"closing: {e}; trying again", flush=True)
        time.sleep(1.5)
        cam.refresh("closing")
    raise SystemExit("could not get back to the shooting screen: please close it on the camera by hand")
