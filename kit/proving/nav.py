"""Getting to a row and back: Down to a submenu row by its label, Right into each submenu, back to the row after a
download closed the menu (by its place, else its label, else by the page scan), the short way round a list, out of
whatever is open with MENU (never OK), and back to the shooting screen.

QUIET_SHOOTING, CYCLE and MODEL are the run's: a checklist prover sets nav.QUIET_SHOOTING while a DISP Set row is
proved, and main() fills CYCLE and MODEL from the page scan."""
import contextlib
import re
import time

from camkit import ocr, safety, screen, vlm
from camkit.link import LinkError
from camkit.screen import same_position, same_state
from camkit.session import osd_shooting
from crawl_run import go_to

from .base import LOCK_S, Failed
from .screens import SEEN, at_label, bar_text, carousel_text, closest_row, glued, option_key, place, run_tmp_png, same_place

# While a DISP Set row is proved the shooting screen can be in another display mode ("No Disp. Info.":
# no battery icon, so it reads "unknown", 2026-10-30); then a screen that stays "unknown" after the
# menu lock is taken for the shooting screen
QUIET_SHOOTING = False


def shooting_like(s, waited: float | None = None) -> bool:
    return s.kind == "shooting" or (QUIET_SHOOTING and s.kind == "unknown" and (waited is None or waited > LOCK_S + 2))


CYCLE: list = []                 # the page scan's Down cycle and page model, for finding the way back
MODEL: dict = {}


def find_row(cam, label) -> bool:
    """Down to the submenu row labelled `label`. Submenus wrap: if one lap finds no match, go to the
    closest reading when it is clearly closer than every other row's, and remember it."""
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


def enter_path(cam, path, start: int):
    """From path[start]'s row on screen, Right into each submenu and Down to the next label."""
    for label in path[start + 1:]:
        cam.press("right")
        if cam.read().kind != "submenu":
            raise Failed(f"Right on {path[start]!r} opened {cam.read().kind}, not its submenu")
        if not find_row(cam, label):
            raise Failed(f"no row {label!r} in the submenu")


def where_in(cam, path) -> int | None:
    """The deepest path element whose row is under the cursor now."""
    for i in range(len(path) - 1, -1, -1):
        if at_label(cam, "menu" if i == 0 else "submenu", path[i]):
            return i
    return None


def after_download(cam, done_at: float):
    """The camera shows "Saving to the connected device..." just after a download returns and
    closes the menu; wait for that to clear and for the menu lock to pass, then MENU if closed."""
    time.sleep(1.0)
    while True:
        s = cam.refresh("after-download")
        waited = time.monotonic() - done_at
        if waited > LOCK_S and (s.kind in ("menu", "submenu") or shooting_like(s, waited)):
            break
        if waited > 25:
            raise Failed(f"after a download the camera stayed on a {s.kind} screen")
        time.sleep(0.4)
    if shooting_like(s):
        cam.press("menu")


def to_row(cam, path, top=None, row_place=None):
    """Back to the row after MENU reopened the menu: by position (the row's own place, or its
    top-level row's), else by label. Labels alone fail: the icon cleanup reads "WB " in "WB Capt.
    Frame Size" as an icon (2026-10-29)."""
    for _ in range(3):
        # MENU can go unanswered after a heavier change (Picture Profile = PP4 left the shooting screen
        # up, 2026-10-29): look again at a fresh frame, and only then press it once more. A slow menu
        # must not get a second MENU: that closed it again and the next Right, on the shooting
        # screen, opened ISO (the wheel's Right; PP3, 2026-10-29)
        if not shooting_like(cam.read()):
            break
        time.sleep(1.5)
        if not shooting_like(cam.refresh("menu-check")):
            break
        cam.press("menu")
    if cam.read().kind not in ("menu", "submenu", "tiles"):
        raise Failed(f"MENU did not bring the menu back ({cam.read().kind}, {cam.frame.path.name})")
    here = place(cam)
    if same_place(here, row_place):
        return
    if same_place(here, top):
        enter_any(cam, path, 0)
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
    enter_any(cam, path, i)


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


def enter_pp(cam, path):
    """From the Picture Profile row: Right into the carousel, Down to PP1, Right into its panel (this
    commits PP1 as the Picture Profile), then into submenus and down to the row."""
    if cam.read().kind != "menu" or not at_label(cam, "menu", path[0]):
        raise Failed(f"not on the Picture Profile row ({cam.read().kind}, {cam.frame.path.name})")
    cam.press("right")
    if cam.read().kind != "dialog":
        raise Failed(f"Right on Picture Profile opened {cam.read().kind}, not its carousel")
    for _ in range(14):
        time.sleep(0.4)
        cam.refresh("reread")
        if option_key(carousel_text(cam)) == option_key(path[1]):
            break
        cam.press("down")
    else:
        raise Failed(f"the Picture Profile carousel never showed {path[1]!r}")
    cam.press("right")
    if cam.read().kind != "submenu":
        raise Failed(f"Right on {path[1]} opened {cam.read().kind}, not its panel")
    for k, label in enumerate(path[2:]):
        if not find_row(cam, label):
            raise Failed(f"no row {label!r} in {' > '.join(path[:2 + k])}")
        if k < len(path) - 3:
            cam.press("right")
            if cam.read().kind != "submenu":
                raise Failed(f"Right on {label!r} opened {cam.read().kind}, not its submenu")


def enter_any(cam, path, start: int):
    if path[0] == "Picture Profile" and len(path) > 2 and re.fullmatch(r"PP\d+", path[1]) and start == 0:
        enter_pp(cam, path)
    else:
        enter_path(cam, path, start)


def to_shooting(link, hdmi, why: str, tries: int = 6):
    """Back to the shooting screen with MENU (cleanup presses: OK only on an information notice that
    refuses MENU and names no identity or credentials, never on a --network run), looking after each press.
    After a row failed on a screen the reader misread, the cancel can stop short (a PP carousel left
    open, 2026-10-29); this run holds the only remote connection, so it must close what is open
    itself rather than wait for a hand on the camera. Falls back to waiting if MENU does not do it."""
    for _ in range(tries):
        f = hdmi.grab(save=False)
        kind = screen.read(f).kind
        if kind == "shooting" or (kind == "unknown" and osd_shooting(link, f)):
            return
        try:
            link.press("menu", cleanup=True)
        except LinkError as e:
            # an information notice can take only OK ("not available as follows Picture Profile On":
            # MENU was refused and the run crashed before its restore, 2026-10-29). OK it when its
            # text is no confirmation and names no identity or credentials ("Connect to <SSID>?"); never otherwise,
            # and never on a --network run (camkit.vlm.LOCAL_ONLY): a row a decision opened may be behind it, whose
            # look-only lock this press, sent straight through the link, would pass by (docs/decisions/0008). The
            # wait below then fails closed
            text = ""
            if kind == "notice" and not vlm.LOCAL_ONLY:
                tmp = run_tmp_png(f)
                try:
                    text = ocr.text_in(ocr.read([tmp])[tmp], (0, 0, 640, 480))
                finally:
                    tmp.unlink(missing_ok=True)
            if kind == "notice" and text and not safety.confirmation(text) and not vlm.LOCAL_ONLY \
                    and not safety.identity_screen(text):
                print(f"   an information notice took only OK: {text[:70]!r}", flush=True)
                link.press("enter", cleanup=True, screen=kind)       # on the notice read: the link's guards judge it
            elif kind == "notice" and (vlm.LOCAL_ONLY or safety.identity_screen(text)):
                why = "a --network run sends it no OK" if vlm.LOCAL_ONLY else "it names identity or credentials"
                print(f"   an information notice refused MENU, and {why} (its text withheld); waiting", flush=True)
                time.sleep(3.0)
            else:
                print(f"   MENU refused ({e}); waiting", flush=True)
                time.sleep(3.0)             # a busy camera (after a heavy profile change) answers later
        time.sleep(1.2)
    end = time.monotonic() + 300            # nobody may be at the camera (overnight): give up, do not hang
    last_menu = time.monotonic()
    while time.monotonic() < end:
        f = hdmi.grab(save=False)
        if screen.read(f).kind == "shooting" or osd_shooting(link, f):
            return
        if time.monotonic() - last_menu > 20:          # a slow camera may need one more MENU
            last_menu = time.monotonic()
            with contextlib.suppress(LinkError):
                link.press("menu", cleanup=True)
        time.sleep(1.0)
    raise Failed(f"no shooting screen for {why} after MENU and 5 minutes")
