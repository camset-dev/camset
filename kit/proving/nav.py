"""Getting to a row and back: Down to a submenu row by its label, Right into each submenu, back to the row after a
download closed the menu (by its place, else its label, else by the page scan), the short way round a list, out of
whatever is open with MENU (never OK), and back to the shooting screen, out of the camera's playback view with its
Playback button pressed once (leave_playback, docs/decisions/0021).

QUIET_SHOOTING, CYCLE and MODEL are the run's: a checklist prover sets nav.QUIET_SHOOTING while a DISP Set row is
proved, and main() fills CYCLE and MODEL from the page scan."""
import contextlib
import re
import time

from camkit import live, ocr, reading, safety, screen, vlm
from camkit.link import CameraRefused, LinkError, StopRequested
from camkit.screen import same_position, same_state
from camkit.session import kind_seen, osd_shooting, playback_kind
from crawl_run import go_to
from camkit.live import menu_from_shooting

from .base import LOCK_S, Failed, LockSeen, lock_log, lock_measured, lock_over
from .screens import SEEN, at_label, bar_text, carousel_text, closest_row, glued, option_key, place, run_tmp_png, same_place

# While a DISP Set row is proved the shooting screen can be in another display mode ("No Disp. Info.":
# no battery icon, so it reads "unknown", 2026-10-30); then a screen that stays "unknown" after the
# menu lock is taken for the shooting screen
QUIET_SHOOTING = False


def shooting_like(s, waited: float | None = None) -> bool:
    return s.kind == "shooting" or (QUIET_SHOOTING and s.kind == "unknown" and (waited is None or waited > LOCK_S + 2))


CYCLE: list = []                 # the page scan's Down cycle and page model, for finding the way back
MODEL: dict = {}


def find_row(cam, label, at=None) -> bool:
    """Down to the submenu row labelled `label`. Submenus wrap: if one lap finds no match, go to the
    closest reading when it is clearly closer than every other row's, and remember it. With `at`, the row's
    place as this run saw it (to_row's row_place): Down until the cursor is at that place (place: the page's
    picture and the cursor's row, no OCR), the label read there once; a place that does not read as the label
    (a submenu that scrolls keeps its page and cursor row), or never comes, is walked by label from where the
    cursor is. A reading a row cost 0.22 s (the speed review of 2026-11-18). Every Down is read and judged as
    ever, and the Right after it checks the live bar against the never-open list."""
    if at is not None and cam.read().kind == "submenu":
        first = cam.read()
        for _ in range(20):
            if same_place(place(cam), at):
                if at_label(cam, "submenu", label):
                    return True
                break
            cam.press("down")
            if same_state(cam.read(), first):
                break
    first = cam.read()
    texts = []
    for _ in range(20):
        if at_label(cam, "submenu", label):
            return True
        texts.append(bar_text(cam))
        cam.press("down")
        if same_state(cam.read(), first):
            break
    best = closest_row(texts, glued(label))
    if best is None:
        return False
    for _ in range(best):                           # back at the first row: Down to the closest
        cam.press("down")
    SEEN[label] = bar_text(cam)
    # a --network or --owner run (local readers only) says no text read off the screen: a bar can carry a value
    seen = "(its text withheld)" if vlm.LOCAL_ONLY else repr(SEEN[label])
    print(f"   row {label!r} reads {seen} here", flush=True)
    return True


def enter_path(cam, path, start: int, at=None):
    """From path[start]'s row on screen, Right into each submenu and Down to the next label; the last by its place
    `at` where this run knows it (find_row)."""
    for k, label in enumerate(path[start + 1:], start + 1):
        cam.press("right")
        if cam.read().kind != "submenu":
            raise Failed(f"Right on {path[start]!r} opened {cam.read().kind}, not its submenu")
        if not find_row(cam, label, at=at if k == len(path) - 1 else None):
            raise Failed(f"no row {label!r} in the submenu")


def where_in(cam, path) -> int | None:
    """The deepest path element whose row is under the cursor now."""
    for i in range(len(path) - 1, -1, -1):
        if at_label(cam, "menu" if i == 0 else "submenu", path[i]):
            return i
    return None


def after_download(cam, done_at: float):
    """The camera shows "Saving to the connected device..." just after a download returns and
    closes the menu; wait for that to clear and for the menu lock to pass, then MENU if closed. The looks
    every 0.4 s are not saved (LiveCamera.glance); the one that decides is, and becomes the camera's frame
    (refresh(frame=)): 70,638 frames of these looks sat in kit2_pass2 (the speed review of 2026-11-18). The lock is
    over by camkit.session.lock_over on what the looks have seen: with HDMI eyes in a mode measured, at the shooting
    screen (or a menu page) after the notice, the looks every 0.1 s from the download's reply; else once LOCK_S has
    passed on the shooting screen or a menu page, the looks from 1 s every 0.4 s, as always."""
    eyes = getattr(cam, "hdmi", None)
    measured = lock_measured(eyes)
    time.sleep(0.0 if measured else 1.0)
    seen = LockSeen()
    while True:
        f, s = cam.glance("after-download")
        waited = time.monotonic() - done_at
        ready = s.kind in ("menu", "submenu") or shooting_like(s, waited)
        seen.see("shooting" if ready else s.kind)
        why = lock_over(waited, seen, eyes) if ready else ""
        if why:
            lock_log(eyes, why, waited)
            break
        if waited > 25:
            cam.refresh("after-download", frame=f)
            raise Failed(f"after a download the camera stayed on a {s.kind} screen")
        time.sleep(0.1 if measured else 0.4)
    s = cam.refresh("after-download", frame=f)
    if shooting_like(s):
        cam.press("menu")


def to_row(cam, path, top=None, row_place=None):
    """Back to the row after MENU reopened the menu: by position (the row's own place, or its
    top-level row's), else by label. Labels alone fail: the icon cleanup reads "WB " in "WB Capt.
    Frame Size" as an icon (2026-10-29)."""
    # MENU can go unanswered after a heavier change (Picture Profile = PP4 left the shooting screen up, 2026-10-29):
    # the one helper looks again at a fresh frame (a menu page at once over HDMI), and only then presses it once more. A
    # slow menu must not get a second MENU: that closed it again and the next Right, on the shooting screen, opened ISO
    # (the wheel's Right; PP3, 2026-10-29). after_download has sent the first MENU
    menu_from_shooting(cam, pressed=True, shooting=shooting_like, clock=time)
    if cam.read().kind not in ("menu", "submenu", "tiles"):
        raise Failed(f"MENU did not bring the menu back ({cam.read().kind}, {cam.frame.path.name})")
    here = place(cam)
    if same_place(here, row_place):
        return
    if same_place(here, top):
        enter_any(cam, path, 0, at=row_place)
        return
    i = where_in(cam, path)
    if i is None:
        # MENU can reopen elsewhere: from the shooting screen the camera does not come back to the
        # Playback tab (Image Order reopened on Network 41/65, 2026-10-29). Find where it is in the
        # page scan and go to the row from there.
        j = next((k for k, p in enumerate(CYCLE) if same_position(cam.read(), p["screen"])), None) if CYCLE else None
        if j is None or go_to(cam, CYCLE, MODEL, j, path[0]) is None:
            raise Failed(f"MENU reopened on a screen that is not on the way to {' > '.join(path)}")
        i = 0
    enter_any(cam, path, i, at=row_place)


def move_to(cam, cur: int, k: int, n: int, kind: str = "list"):
    d = (k - cur) % n
    key, steps = ("down", d) if d <= n - d else ("up", n - d)
    for _ in range(steps):
        cam.press(key)
        if cam.read().kind != kind:
            raise Failed(f"{key} in the {kind} left it ({cam.read().kind})")


def cancel(cam, link):
    """Out of whatever is open, never with OK."""
    cam.cancel_to_menu()


PP_LAP = 30            # at most this many carousel options read on the way round (Movie's Picture Profile holds 13)


def enter_pp(cam, path, at=None):
    """From the Picture Profile row: Right into the carousel, Down until the option under the cursor is the profile
    path[1], Right into its panel (this commits that profile as the Picture Profile), then into submenus and down to
    the row (by its place `at` where this run knows it: find_row). The option is the profile where its reading is the
    name (option_key) or the same short code, a digit's look-alike read as that digit (camkit.reading.code_same: "PРЗ",
    a Cyrillic Er and a Cyrillic Ze, is PP3; 2026-11-18, Movie over HDMI). The carousel is walked until the first option
    read comes round again (PP_LAP at most), so its length is the camera's: a profile it does not hold fails after one
    lap, and a reading of nothing ends no lap. No reading's text is said (the option it opens on is the one in use)."""
    if cam.read().kind != "menu" or not at_label(cam, "menu", path[0]):
        raise Failed(f"not on the Picture Profile row ({cam.read().kind}, {cam.frame.path.name})")
    cam.press("right")
    if cam.read().kind != "dialog":
        raise Failed(f"Right on Picture Profile opened {cam.read().kind}, not its carousel")
    first = None
    for n in range(PP_LAP):
        time.sleep(0.4)
        cam.refresh("reread")
        t = carousel_text(cam)
        if option_key(t) == option_key(path[1]) or reading.code_same(t, path[1]):
            break
        if first is not None and t.strip() and reading.code_same(t, first):
            raise Failed(f"the Picture Profile carousel never showed {path[1]!r}: it came round to the option it "
                         f"opened on after {n} options ({cam.frame.path.name})")
        first = first if first is not None or not t.strip() else t
        cam.press("down")
    else:
        raise Failed(f"the Picture Profile carousel never showed {path[1]!r} in {PP_LAP} options")
    cam.press("right")
    if cam.read().kind != "submenu":
        raise Failed(f"Right on {path[1]} opened {cam.read().kind}, not its panel")
    for k, label in enumerate(path[2:]):
        if not find_row(cam, label, at=at if k == len(path) - 3 else None):
            raise Failed(f"no row {label!r} in {' > '.join(path[:2 + k])}")
        if k < len(path) - 3:
            cam.press("right")
            if cam.read().kind != "submenu":
                raise Failed(f"Right on {label!r} opened {cam.read().kind}, not its submenu")


def enter_any(cam, path, start: int, at=None):
    """From path[start]'s row on screen down to the path's last row (enter_path, or enter_pp for a PP's panel), that
    row by its place `at` where this run knows it (to_row's row_place)."""
    if path[0] == "Picture Profile" and len(path) > 2 and re.fullmatch(r"PP\d+", path[1]) and start == 0:
        enter_pp(cam, path, at=at)
    else:
        enter_path(cam, path, start, at=at)


LEAVE_S = 3.0           # s leave_playback looks for the shooting screen after its one press


def leave_playback(link, eyes, wait: float = LEAVE_S) -> bool:
    """Out of the camera's playback view with its Playback button, pressed once (docs/decisions/0021): only where the
    screen read just now is that view (camkit.session.kind_seen gives "playback": read as the shooting screen while the
    camera says it is in Playback, Link.in_playback True), never over a menu, a dialog, a notice or a screen of no known
    kind. The link judges the press again (Link.press_playback: the screen it is given is the playback view and the
    camera says Playback), and lets the Playback button out for this call alone. Then looks again, for up to `wait` s,
    until the camera says it is not in Playback (in_playback False) and the screen reads as the shooting screen. True
    when that happened; False otherwise, with nothing more pressed: the screen was not the playback view, the press was
    refused (a STOP among the reasons: it is no cleanup press) or went unanswered, or the camera stayed in Playback."""
    try:
        f = eyes.grab(save=False)
        kind = kind_seen(link, f)
    except Exception as e:      # noqa: BLE001 (a screen that cannot be read is no playback view)
        kind = f"unread ({type(e).__name__})"
    if kind != "playback":
        return False
    try:
        link.press_playback(screen=kind)
    except (safety.Refused, LinkError, StopRequested) as e:
        print(f"   the Playback button did not go out to leave the playback view: {type(e).__name__}", flush=True)
        return False
    end = time.monotonic() + wait
    while True:
        time.sleep(0.3)
        try:
            f = eyes.grab(save=False)
            s = screen.read(f)
            back = (s.kind == "shooting" or osd_shooting(link, f)) and link.in_playback() is False
        except Exception:   # noqa: BLE001 (a look that fails is no shooting screen)
            back = False
        if back:
            return True
        if time.monotonic() >= end:
            print(f"   the camera still shows its playback view {wait:.0f} s after the Playback button", flush=True)
            return False


def to_shooting(link, hdmi, why: str, tries: int = 6):
    """Back to the shooting screen with MENU (cleanup presses: OK only on a notice that has just refused MENU, asks
    nothing by its shape and shows OK as its only button, and names no identity or credentials, never on a --network
    run), looking after each press.
    After a row failed on a screen the reader misread, the cancel can stop short (a PP carousel left
    open, 2026-10-29); this run holds the only remote connection, so it must close what is open
    itself rather than wait for a hand on the camera. Falls back to waiting if MENU does not do it.
    Where a MENU it sent leaves the camera on its playback view (camkit.session.kind_seen: read as the shooting screen
    while the camera says it is in Playback), leave_playback presses the Playback button once instead of another MENU;
    when that does not bring the shooting screen, to_shooting ends there, Failed, with no other key pressed and no
    wait."""
    pressed = False
    for _ in range(tries):
        f = hdmi.grab(save=False)
        seen = screen.read(f)
        kind = playback_kind(link, "shooting" if seen.kind == "unknown" and osd_shooting(link, f) else seen.kind)
        if kind == "shooting":
            return
        if kind == "playback" and pressed:
            if leave_playback(link, hdmi):
                return
            # nothing more is pressed, and no wait: MENU there only opens and closes the menu over the view
            raise Failed(f"the camera stayed in its playback view for {why}: nothing more was pressed")
        try:
            link.press("menu", cleanup=True)
            pressed = True                  # a MENU the camera took: the playback view after it is MENU's doing
        except LinkError as e:
            # an information notice can take only OK ("not available as follows Picture Profile On":
            # MENU was refused and the run crashed before its restore, 2026-10-29). OK it only where the camera itself
            # refused MENU ("button not accepted": CameraRefused; never a MENU left held, nor one never answered, which
            # may have gone), on the screen looked at again after that refusal and found the same (live.look_again),
            # judged there as camkit.live.LiveCamera judges a notice that has just refused MENU (live.menu_refused_enter:
            # no question mark, OK plainly its only button and reading OK, no confirmation's words), and where its text
            # names no identity or credentials ("Connect to <SSID>?"); never otherwise, and never on a --network run
            # (camkit.vlm.LOCAL_ONLY): a row a decision opened may be behind it, whose look-only lock this press, sent
            # straight through the link, would pass by (docs/decisions/0008). The OK carries the link's count of moving
            # commands at that judgement (Link.press's judged). The wait below then fails closed
            text, refused_by = "", ""
            refused_menu = isinstance(e, CameraRefused)
            if kind == "notice" and not vlm.LOCAL_ONLY and refused_menu:
                stale, again = live.look_again(hdmi, seen, "menu-refused", getattr(link, "moved_at", None))
                if stale:
                    refused_by = stale
                else:
                    tmp = run_tmp_png(again)
                    try:
                        text = ocr.text_in(ocr.read([tmp])[tmp], (0, 0, 640, 480))
                        refused_by = live.menu_refused_enter(kind, again.image, tmp)
                    finally:
                        tmp.unlink(missing_ok=True)
            judged_at = getattr(link, "moves", None)
            if kind == "notice" and refused_menu and text and not refused_by and not vlm.LOCAL_ONLY \
                    and not safety.identity_screen(text):
                print(f"   a notice refused MENU and shows OK alone: OK ({text[:70]!r})", flush=True)
                # judged above as LiveCamera judges a notice that has just refused MENU: the link's guards judge it too
                link.press("enter", cleanup=True, screen=kind, judged=judged_at)
            elif kind == "notice" and refused_menu and (vlm.LOCAL_ONLY or safety.identity_screen(text)):
                why = "a --network run sends it no OK" if vlm.LOCAL_ONLY else "it names identity or credentials"
                print(f"   an information notice refused MENU, and {why} (its text withheld); waiting", flush=True)
                time.sleep(3.0)
            elif kind == "notice" and refused_by:
                print(f"   a notice refused MENU, and no OK goes on it: {refused_by}; waiting", flush=True)
                time.sleep(3.0)
            else:
                print(f"   MENU refused ({e}); waiting", flush=True)
                time.sleep(3.0)             # a busy camera (after a heavy profile change) answers later
        time.sleep(1.2)
    end = time.monotonic() + 300            # nobody may be at the camera (overnight): give up, do not hang
    last_menu = time.monotonic()
    while time.monotonic() < end:
        f = hdmi.grab(save=False)
        if kind_seen(link, f) == "shooting":
            return
        if time.monotonic() - last_menu > 20:          # a slow camera may need one more MENU
            last_menu = time.monotonic()
            with contextlib.suppress(LinkError):
                link.press("menu", cleanup=True)
        time.sleep(1.0)
    raise Failed(f"no shooting screen for {why} after MENU and 5 minutes")
