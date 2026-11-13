"""Drive one row by hand-written presses, with evidence: for screens no walker reads yet.

    .venv/bin/python -u kit/drive.py --path "External Flash Set." --path "Ext. Flash Firing Set." \\
        --press right --press "enter:flash control mode" --run kit2_flash

Goes to the row (the top-level label, then each submenu label), sends the presses in order, saves
every frame with its text, closes back to the shooting screen, and diffs the settings downloaded
before and after. A press written "key:regex" is sent only when the screen's text matches the regex
(case-insensitive); otherwise the screen is cancelled with MENU. "key@y" presses key until the
orange cursor bar covers screen row y (none if it already does; at most 8): screens that reopen
on the row used last need it (Ext. Flash Cust. Set.); it moves the cursor only, so Enter, Right, C4 and a dial are
refused in that form, and a regex after it ("down@367:REGEX") is checked first. Enter (and the multi-selector's
centre) always needs a regex. A key is judged and sent as camkit.safety names it, whatever its spelling (" enter",
"Enter", quoted, a look-alike letter: canonical_key), and anything that is not a key is refused before anything
connects. The guards fail closed
(press_refused): Enter is refused when the lit text cannot be read, when it reads Initialize or Reset Network
Set., when the screen reads either and the lit text is not Camera Settings Reset, and on a screen that reads
like a confirmation (safety.confirmation) unless --confirm is given, which never lifts the rest. Right or Enter
onto a lit row on the never-open list is refused unless --allow names it, and Right on a menu page whose lit
row cannot be read is refused.
"enter!:regex" is Enter vouched by the operator (2026-11-09), for a screen that lights nothing the kit can read (the a1
II's MR Memory slots) although the operator looking at the frame can see what the cursor is on. The a1 II's owner
allowed it on their own camera (2026-11-09, with any button but the delete key while a picture is shown); on another
camera, only with its owner's word: the public rules stand (AGENTS.md; docs/decisions/0007, C4 only as guarded Help and
C1-C3, C5-C7 never; 0002, sound, light and motion by hand). The screen must match the regex; then, when nothing lit can
be read, the press goes ahead only on a screen that is no menu, submenu, Main tiles or shooting screen (Enter there opens
a row nobody read: VOUCH_REFUSED), whose whole text reads something (a regex such as ".*" matches a blank screen too)
and whose whole text names nothing on the never-open list (safety.screen_refused: an
action, credentials, a by-hand row, sound, light or motion; a name --allow gives lifts its own words, never the cards,
Initialize, Reset Network Set., credentials or the camera's identity, a connection or its region). The log line and
drive.jsonl say "vouched". Only the unreadable lit text
is lifted: the never-open list, Initialize, Reset Network Set., the confirmation check (--confirm) and C4 stay as they
are (press_decision).
"help" presses C4 (the trash button) for the In-Camera Guide, only on a menu or option screen whose
footer draws the help button; Enter on its popup only on "In-Camera Guide", never Add to My Menu.
--grip up|down (the camera held vertically, 2026-11-02): dialogs opened from the menu turn on screen while
the menu pages stay level, so each screen is read both as it is and turned upright (as kit/provers/orient_run.py
does), and a press's regex may match either.
"c4set" presses C4 on Focus Area's screen with Custom 1-3 lit, where the button reads SET and opens the
custom box's size editor (and, in the editor, puts the default size back). Nowhere else, never on the shooting screen
or in Playback, where C4 deletes.
"c4reset" presses C4 on a Creative Look's panel whose footer reads Reset.
Both are go-aheads an owner gives for their own body (the a1 II's owner gave them on 2026-11-02 and 2026-11-03), never a
default: a run sends one only when --c4-press names it (--c4-press c4set, --c4-press c4reset), the owner's word for this
run, and a --press using one without it is refused before anything connects; the word is said in the console, the
run's events.jsonl and drive.jsonl, as --on-shooting's is. "help" (guarded Help) needs no word: AGENTS.md allows it.
Rows on the never-open list are refused unless named with --allow; no --allow opens anything on the cards,
Initialize, Reset Network Set., a credentials screen or the camera's identity, a connection or its region (decision 8:
safety.allow_refused, judged on every --allow and every --path label before anything connects, and safety.never_lifted
on the camera). A path "Picture Profile", "PP3", ... opens that profile's own panel (opening it makes it the Picture
Profile in use).
On the shooting screen a key does what the body makes of it (decision 21): a --press that meets the
shooting screen, a "key@y" press among them, is refused there, and the screen cancelled, unless --on-shooting names the
key (for a dial turn, its dial: "--on-shooting front"), the owner's word for that key, said in the console line, the
run's events.jsonl and drive.jsonl; MENU needs no naming, and C4 is never sent there whatever is named (decision 7).
A key named so is judged on the shooting screen by that naming: the refusals of a Right or an Enter whose lit row
cannot be read are for screens with rows, and the shooting screen has none to open (press_refused's on_shooting);
Enter there still meets the Initialize and confirmation checks. camkit.link refuses any other key there too, unless
named for the press. A key named for the shooting screen changes what no settings file holds (a focus frame's place,
the live exposure): the run's restore does not put it back, so the operator names, and presses, the keys that do (a
frame moved with ms_left is put back with ms_right, both named).
Results: runs/<model>_fw<fw>/<run>/drive.jsonl; frames and downloads in the same run folder. The settings are downloaded before
and after; the diff is kept with the result, and if anything changed the start file is uploaded and the restore
checked (docs/decisions/0015: every run ends restoring its start file).
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ocr, safety, screen, session  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.live import LiveCamera, lit_text, open_refused, press, text_of  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.session import wait_for  # noqa: E402
from crawl_run import find_position, go_to  # noqa: E402
from prove_run import enter_any  # noqa: E402
from runner import (EXIT_UNRESTORED, add_scan_argument, changes_of, close_for_restore, load_scan,  # noqa: E402
                    restore_checked, restoring)


def bar_at(cam, y: int) -> bool:
    return lit_at(cam.frame.image, y)


def lit_at(image, y: int) -> bool:
    """The orange cursor covers screen row y: a menu row's bar (0.6-0.7 of the width) or a dialog's
    button (Enter / Cancel, a third of it: 0.33); orange value text stays under 0.05 (2026-11-01)."""
    return float(screen._orange(image)[y, 20:600].mean()) > 0.25


def highlighted(image, path) -> str:
    """The text inside the orange cursor (a row or a button), or "" when nothing is lit."""
    return lit_text(image, path)


# never pressed by any run, whatever --allow or --confirm say: Initialize wipes the network
# identity and the remote link, and the user keeps it by hand (2026-11-01)
NEVER_ENTER = re.compile(r"initiali[sz]e|reset network", re.I)
# the one reset decision 5 allows, which shares its screen with Initialize (Setting Reset's two rows)
CAMERA_SETTINGS_RESET = re.compile(r"camera\s+settings?\s+reset", re.I)
ENTERS, RIGHTS = ("enter", "ms_enter"), ("right", "ms_right")
# screens where Right opens the lit row: there the row must be read before it is opened
ROW_KINDS = ("menu", "submenu", "tiles", "shooting", "unknown")
# screens where no Enter is vouched for (enter!:regex): Enter opens their lit row, which must be read. An unknown screen
# is not among them, for the MR Memory slots read as one (kit2_small_1109); there the regex and the whole screen's text
# (safety.screen_refused) are the guard
VOUCH_REFUSED = ("menu", "submenu", "tiles", "shooting")


C4_PRESSES = ("help", "c4set", "c4reset")
# the C4 presses an owner allows for their own body, each only with --c4-press naming it (the owner's word, per run)
C4_OWNER_PRESSES = {"c4set": "Focus Area's SET", "c4reset": "a Creative Look panel's Reset"}
DIAL = re.compile(r"dial\.([a-z_]+)\.(-?[0-9]+)")


def canonical_key(raw: str) -> str | None:
    """A --press key as the guards judge it and the link sends it: the spaces and quotes around it left out, the case
    folded, look-alike letters as the Latin ones they are drawn as (safety.fold), so " enter", '"Enter"' and a
    Cyrillic "еnter" are all Enter, judged as Enter and sent as Enter (the folding is camkit.safety.canonical_input's,
    the one the link's guard reads names by). The link's parser drops spaces and quotes itself, so " enter" once
    passed every check here and still reached the camera as Enter. None when what is left is no key drive.py sends: a
    menu input (camkit.safety.MENU_INPUTS), a C4 press (help, c4set, c4reset) or a dial turn (dial.NAME.STEPS on a
    menu dial)."""
    k = safety.canonical_input(raw)
    if k in safety.MENU_INPUTS or k in C4_PRESSES:
        return k
    m = DIAL.fullmatch(k)
    return k if m and m.group(1) in safety.MENU_INPUTS else None


def vouched_press(p: str) -> bool:
    """True for a press written "enter!:regex": the operator vouches for Enter when nothing lit can be read."""
    return p.partition(":")[0].strip().strip(safety.QUOTES).endswith("!")


def parse_press(p: str) -> tuple:
    """(key, y, regex) of a --press argument: the key as canonical_key gives it (None when it is no key), y the screen
    row of "key@y" as written (None without an @), the regex what follows the first ":" ("" without). A "!" after
    the key (vouched_press) is not part of it."""
    head, _, want = p.partition(":")
    raw, at, y = head.strip().strip(safety.QUOTES).partition("@")
    return canonical_key(raw.removesuffix("!")), (y.strip() if at else None), want


def press_args_refused(presses: list) -> str:
    """Why the --press arguments are refused before anything connects, or "". A key must be one drive.py sends, in
    any spelling canonical_key folds to one; Enter and the multi-selector's centre need a regex the screen must
    match, and so does a dial; "key@y" only moves the cursor, so it takes no key that opens, chooses or turns (Enter,
    Right, C4, a dial), and y is a screen row (ASCII digits)."""
    for p in presses:
        key, y, want = parse_press(p)
        if key is None:
            return (f"{p!r}: not a key drive.py sends (the menu inputs as camkit.safety names them: up, down, left, "
                    f"right, enter, menu, ms_..., wheel, front, rear_l, rear_r; help, c4set, c4reset; "
                    f"dial.NAME.STEPS)")
        if vouched_press(p) and (key not in ENTERS or y is not None or not want):
            return f"{p!r}: only Enter can be vouched for, as enter!:regex"
        if y is not None:
            if key in ENTERS + RIGHTS or key in C4_PRESSES or key.startswith("dial."):
                return f"{p!r}: key@y only moves the cursor; {key!r} opens, chooses or turns, and is sent once with a regex"
            if not re.fullmatch(r"[0-9]+", y):
                return f"{p!r}: key@y wants a screen row (a number) after the @"
            continue
        if key in ENTERS and not want:
            return f"{p!r}: Enter needs a regex the screen must match (key:regex)"
        if key.startswith("dial.") and not want:
            return f"{p!r}: a dial turn needs a regex the screen must match (dial.NAME.STEPS:regex)"
    return ""


def on_shooting_refused(keys: list) -> str:
    """Why the --on-shooting keys are refused before anything connects, or "": each must be a key or a dial the link
    takes (camkit.safety.MENU_INPUTS), in any spelling canonical_key folds to one; MENU needs no naming, and C4 is never
    sent on the shooting screen whatever is named (decision 7)."""
    for raw in keys:
        k = safety.canonical_input(raw)
        if k in safety.SHOOTING_FREE:
            return f"--on-shooting {raw!r}: MENU goes out on the shooting screen without being named"
        if k == "c4" or k in C4_PRESSES:
            return f"--on-shooting {raw!r}: C4 is never pressed on the shooting screen (docs/decisions/0007)"
        if k not in safety.MENU_INPUTS:
            return (f"--on-shooting {raw!r}: not a key or a dial the link takes (the menu inputs as camkit.safety names "
                    "them: up, down, left, right, enter, ms_..., wheel, front, rear_l, rear_r)")
    return ""


def c4_presses_refused(presses: list, allowed) -> str:
    """Why the --press arguments are refused before anything connects, or "": a c4set or c4reset press needs --c4-press
    naming it (`allowed`), the owner's word for this run; guarded Help ("help") needs none."""
    for p in presses:
        key = parse_press(p)[0]
        if key in C4_OWNER_PRESSES and key not in allowed:
            return (f"{p!r}: C4 as {C4_OWNER_PRESSES[key]} is a go-ahead an owner gives for their own body, never a "
                    f"default: only with your owner's word for this run, --c4-press {key}")
    return ""


def press_name(key: str) -> str:
    """The name a --press key (as canonical_key gives it) is named by for the shooting screen: a dial turn's dial,
    else the key."""
    m = DIAL.fullmatch(key)
    return m.group(1) if m else key


def shooting_press_refused(key: str, kind: str, on_shooting=()) -> str:
    """Why drive.py may not send the --press key `key` (as canonical_key gives it) on a screen read as `kind`, or "":
    on the shooting screen no key but MENU, unless --on-shooting names it (`on_shooting`, keys as canonical_input gives
    them; a dial turn is named by its dial) (decision 21)."""
    name = press_name(key)
    if kind != "shooting" or name in safety.SHOOTING_FREE or name in on_shooting:
        return ""
    return (f"the screen is the shooting screen, where {name!r} does what the body makes of it: only with the owner's "
            f"word, --on-shooting {name}")


def press_refused(key: str, lit: str, text: str, kind: str, confirm: bool = False, allow=(),
                  vouched: bool = False, on_shooting=()) -> str:
    """Why drive.py may not send this press, or "" when it may. Fails closed: a lit text that cannot be read is
    no permission (decisions 5 and 9). lit: the text in the orange cursor (highlighted); text: the whole screen's.
    --confirm (confirm) allows Enter on a confirmation, never on Initialize or Reset Network Set. The key is judged as
    canonical_key folds it (" enter" is Enter), and one that is no key is refused.
    vouched (enter!:regex): the operator vouches for Enter, so an unreadable lit text alone does not refuse it, on a
    screen that is not in VOUCH_REFUSED, whose whole text reads something (a regex such as ".*" matches a blank
    screen too, and a blank text gives screen_refused nothing to judge) and names nothing never-open
    (safety.screen_refused).
    on_shooting (--on-shooting, keys as canonical_input gives them): on a screen read as the shooting screen a key named
    there is judged by that naming (decision 21): it has no row to open, so the refusals of a lit text that cannot be
    read, and the lit row's never-open check, are not made; Enter still meets the Initialize and confirmation checks.
    On every other screen, "unknown" among them, nothing changes."""
    canon = canonical_key(key)
    if canon is None:
        return f"{key!r} is not a key drive.py sends"
    key, lit = canon, (lit or "").strip()
    named = kind == "shooting" and key in on_shooting      # no row on the shooting screen: the naming judges it
    if key in ENTERS and not named:
        if not lit and not vouched:
            return "nothing lit can be read, so the button under the cursor is unknown"
        if not lit and kind in VOUCH_REFUSED:
            return f"nothing lit can be read on a {kind!r} screen, where Enter opens a row nobody read: no vouching there"
        if not lit and not re.search(r"\w", text or ""):
            return "nothing lit and nothing on the screen can be read, so nothing tells what Enter would do: no vouching there"
        why = "" if lit else safety.screen_refused(text, allow)
        if why:
            return f"nothing lit can be read and {why}: no vouching there"
    if key in ENTERS:
        if any(NEVER_ENTER.search(r) for r in safety.readings(lit)):
            return f"the cursor is on {lit!r}"
        m = next((m for r in safety.readings(text or "") for m in [NEVER_ENTER.search(r)] if m), None)
        if m and not CAMERA_SETTINGS_RESET.search(lit):
            return f"the screen reads {m.group(0)!r} and the lit text {lit!r} is not Camera Settings Reset"
        if safety.confirmation(text) and not confirm:
            return f"{safety.confirmation(text)} on {(text or '')[:120]!r}"
    if key in RIGHTS and not lit and kind in ROW_KINDS and not named:
        return f"nothing lit can be read on a {kind!r} screen, so the row Right would open is unknown"
    if key in ENTERS + RIGHTS and lit and not named:
        return open_refused(lit, allow)
    return ""


def press_decision(p: str, key: str, lit: str, text: str, kind: str, confirm: bool = False, allow=(),
                   on_shooting=()) -> tuple:
    """(why the press is refused or "", whether it goes as vouched) for the --press `p` whose key is `key`, on a screen
    whose lit text is `lit`, whole text `text` and kind `kind`, as main() sends it: a press written enter!:regex is
    vouched for (press_refused's vouched) only when it is Enter, and goes as vouched only when nothing lit could be
    read and nothing refuses it. on_shooting: the keys --on-shooting named (press_refused)."""
    vouched = vouched_press(p) and key in ENTERS and not (kind == "shooting" and key in on_shooting)    # named instead
    why = press_refused(key, lit, text, kind, confirm, allow, vouched, on_shooting)
    return why, bool(vouched and not why and not (lit or "").strip())


# "help" presses C4, the trash button, which opens the In-Camera Guide on these screens when their
# footer draws the help button (the SDK's Delete key does nothing there, 2026-11-01). Never on the shooting screen or
# the Main tiles, where C4 does whatever the body assigns to it, nor in Playback or with a picture displayed, where it
# deletes (decision 7; Link.press refuses C4 on any screen outside safety.C4_SCREENS as well). Number fields too: ISO
# Range Limit's draws it (the timers' do not)
HELP_SCREENS = safety.C4_HELP_SCREENS
# "c4set": C4 on Focus Area with Custom 1-3 lit ("SET": the box's size editor), and inside that editor
CUSTOM_BOX = re.compile(r"focus area[\s\S]*custom\s*[123]|custom\s*[123][\s\S]*focus area"
                        r"|^\W*custom\s*[123]\b[\s\S]*reset[\s\S]*cancel", re.I)       # the editor: Reset, Cancel, OK


# "c4reset": C4 on a Creative Look's panel, whose footer reads "Reset" on the trash button: it puts the look's
# parameters back (the owner's go-ahead, 2026-11-03). Nowhere else
LOOK_PANEL = re.compile(r"creative look[\s\S]*reset[\s\S]*cancel[\s\S]*ok", re.I)


# np.rot90's k that turns a frame upright (kit/provers/orient_run.py GRIPS)
GRIPS = {"down": -1, "up": 1}


def screen_text(cam, grip: str | None) -> str:
    """The screen's text; held vertically, the text of the frame turned upright follows it."""
    t = text_of(cam)
    if grip:
        import numpy as np
        from PIL import Image
        f = cam.frame
        path = f.path.with_name(f"{f.path.stem}_upright.png")
        Image.fromarray(np.ascontiguousarray(np.rot90(f.image, GRIPS[grip]))).save(path)
        t += " || " + ocr.text_in(ocr.read([path])[path], (0, 0, 480, 640)).strip()
    return t


def c4set_refused(kind: str, text: str) -> str:
    """Why C4 may not be pressed here as Focus Area's SET, or "" when it may."""
    if kind in ("shooting", "tiles") or not CUSTOM_BOX.search(text):
        return f"not Focus Area with Custom 1-3 ({kind})"
    return ""


def c4reset_refused(kind: str, text: str) -> str:
    """Why C4 may not be pressed here as a Creative Look panel's Reset, or "" when it may."""
    if kind in ("shooting", "tiles") or not LOOK_PANEL.search(text) or re.search(r"playback|delete", text, re.I):
        return f"not a Creative Look panel with Reset in its footer ({kind})"
    return ""


def help_refused(kind: str, image) -> str:
    """Why C4 may not be pressed here as Help, or "" when it may."""
    if kind not in HELP_SCREENS:
        return f"the screen is {kind!r}, not a menu or option screen"
    if screen.help_glyph(image) is None:
        return "the footer shows no help button"
    return ""


def shooting_word(cam, run, name: str, on_shooting) -> dict:
    """LiveCamera.press's (or dial's) keywords for a press of `name` (a key, or a dial's name): {"on_shooting": {name}}
    when --on-shooting named it and the screen reads as the shooting screen, the owner's word said in the console and
    the run's events.jsonl as it goes; {} otherwise, so the link refuses it there (decision 21)."""
    if name not in on_shooting or cam.read().kind != "shooting":
        return {}
    print(f"   {name} on the shooting screen: the owner's word (--on-shooting {name})", flush=True)
    run.log("on_shooting_press", key=name, frame=cam.frame.path.name)
    return {"on_shooting": frozenset({name})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", required=True, help="top-level row label, then submenu labels")
    ap.add_argument("--press", action="append", default=[], help="key, or key:regex the screen must match first; enter!:regex is Enter vouched by the "
                    "operator when nothing lit can be read")
    ap.add_argument("--allow", action="append", default=[], help="a never-open label this run may enter")
    ap.add_argument("--on-shooting", action="append", default=[], metavar="KEY",
                    help="a key (or a dial) this run may press on the shooting screen, where a key does what the body "
                         "makes of it: the owner's word, per key")
    ap.add_argument("--c4-press", action="append", default=[], choices=sorted(C4_OWNER_PRESSES),
                    help="the owner's word for this run for a C4 press their own body allows: c4set (Focus Area's SET "
                         "with Custom 1-3 lit), c4reset (a Creative Look panel's Reset)")
    ap.add_argument("--confirm", action="store_true", help="allow Enter on a screen that reads like a confirmation")
    ap.add_argument("--wait", type=float, default=1.0, help="seconds after the last press")
    ap.add_argument("--run", default="kit2_drive")
    ap.add_argument("--note", default="", help="what this drive tests (kept with the result)")
    add_scan_argument(ap)
    ap.add_argument("--grip", choices=sorted(GRIPS), help="the camera is held vertically: read turned screens upright")
    a = ap.parse_args()
    for label in a.allow:
        # nothing on the cards (2026-11-01, the owner: "Please don't delete the cards"), Initialize, Reset Network Set.,
        # credentials, nor the camera's identity, a connection or its region (decisions 4, 5, 8 and 9)
        why = safety.allow_refused(label)
        if why:
            sys.exit(f"--allow {label!r}: {why}")
    for label in a.path:
        hard = safety.allow_refused(label)
        if hard:
            sys.exit(f"{label!r}: {hard}")
        why = safety.never_open(label)
        if why and label not in a.allow:
            sys.exit(f"{label!r} is never-open ({why}); name it with --allow to enter it")
    why = press_args_refused(a.press) or on_shooting_refused(a.on_shooting) or c4_presses_refused(a.press, a.c4_press)
    if why:
        sys.exit(why)
    on_shooting = frozenset(safety.canonical_input(k) for k in a.on_shooting)
    cycle, model = load_scan(a.scan)
    run = Run(a.run)
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    hdmi = eyes_from_config(run)
    log = open(run.dir / "drive.jsonl", "a", encoding="utf-8", newline="\n")  # noqa: SIM115 (closed in the finally below)
    if on_shooting:
        # the owner's word, said where the run's evidence is
        print(f"the owner allowed on the shooting screen: {', '.join(sorted(on_shooting))} (--on-shooting)", flush=True)
        run.log("on_shooting_allowed", keys=sorted(on_shooting))
    c4_allowed = sorted(set(a.c4_press))
    if c4_allowed:
        print(f"the owner allowed C4 as: {', '.join(C4_OWNER_PRESSES[k] for k in c4_allowed)} (--c4-press)", flush=True)
        run.log("c4_allowed", presses=c4_allowed)
    ending = None
    try:
        with Link(run) as link:
            hdmi.attach(link)
            if screen.read(hdmi.grab(save=False)).kind in ("menu", "tiles"):
                link.press("menu", cleanup=True)
                time.sleep(1.0)
            wait_for(hdmi, ("shooting",), "the settings download", link=link)
            before = link.download("before")
            time.sleep(5)
            cam = LiveCamera(link, hdmi, run, may_open=a.allow)
            screens, ok = [], True
            try:
                cam.press("menu")
                j = find_position(cam, cycle, model)
                if j is None or go_to(cam, cycle, model, j, a.path[0]) is None:
                    raise RuntimeError(f"could not reach {a.path[0]!r} by the scan")
                enter_any(cam, a.path, 0)
                for p in a.press:
                    # the key as the guards judge it and as it is sent (canonical_key; press_args_refused saw that
                    # every key is one)
                    key, y, want = parse_press(p)
                    if y is not None:
                        t = screen_text(cam, a.grip) if want else ""
                        if want and not re.search(want, t, re.I):
                            print(f"the screen does not match {want!r}: {t[:160]!r}; cancelling", flush=True)
                            ok = False
                            break
                        refused = ""
                        for _ in range(8):              # a cursor move only: press_args_refused saw to that
                            if bar_at(cam, int(y)):
                                break
                            # each press of the loop judged on its own screen: one may land on the shooting screen
                            refused = shooting_press_refused(key, cam.read().kind, on_shooting)
                            if refused:
                                break
                            press(cam, key, **shooting_word(cam, run, key, on_shooting))
                        if refused:
                            print(f"{key} refused: {refused}; cancelling", flush=True)
                            ok = False
                            break
                        if not bar_at(cam, int(y)):
                            print(f"the cursor bar never reached y={y}; cancelling", flush=True)
                            ok = False
                            break
                        print(f"{p:32s} -> bar at y={y}  {cam.frame.path.name}", flush=True)
                        continue
                    t = screen_text(cam, a.grip)
                    if want and not re.search(want, t, re.I):
                        print(f"the screen does not match {want!r}: {t[:160]!r}; cancelling", flush=True)
                        ok = False
                        break
                    why = shooting_press_refused(key, cam.read().kind, on_shooting)
                    if why:
                        print(f"{key} refused: {why}; cancelling", flush=True)
                        ok = False
                        break
                    # marked "on_shooting" only when --on-shooting named the key and it goes out on the shooting screen
                    shooting = cam.read().kind == "shooting" and press_name(key) in on_shooting
                    lit = highlighted(cam.frame.image, cam.frame.path) if key in ENTERS + RIGHTS else ""
                    if key == "c4set":
                        why = c4set_refused(cam.read().kind, t)
                        if why:
                            print(f"C4 (SET) refused: {why}; cancelling", flush=True)
                            ok = False
                            break
                    if key == "c4reset":
                        why = c4reset_refused(cam.read().kind, t)
                        if why:
                            print(f"C4 (Reset) refused: {why}; cancelling", flush=True)
                            ok = False
                            break
                    if key == "help":
                        why = help_refused(cam.read().kind, cam.frame.image)
                        if why:
                            print(f"Help (C4) refused: {why}; cancelling", flush=True)
                            ok = False
                            break
                    if key in ENTERS and cam.read().kind == "helppop" and not re.search(r"in-?camera guide", lit, re.I):
                        # the popup's other entry, Add to My Menu, writes the file
                        print(f"Enter refused on the help popup: the cursor is on {lit!r}; cancelling", flush=True)
                        ok = False
                        break
                    why, vouched = press_decision(p, key, lit, t, cam.read().kind, a.confirm, a.allow, on_shooting)
                    if vouched:
                        print(f"Enter vouched by the operator on {t[:120]!r}", flush=True)
                    if why:
                        print(f"{key} refused: {why}; cancelling", flush=True)
                        ok = False
                        break
                    if key.startswith("dial."):
                        # "dial.NAME.STEPS:regex": turn a dial, only on the screen the regex names
                        # (on the shooting screen a dial changes the live exposure, which no file holds)
                        _, dname, steps = key.split(".")
                        cam.dial(dname, int(steps), **shooting_word(cam, run, dname, on_shooting))
                    elif key in C4_PRESSES:
                        if key in C4_OWNER_PRESSES:         # c4_presses_refused saw that --c4-press names it
                            print(f"   C4 as {C4_OWNER_PRESSES[key]}: the owner's word (--c4-press {key})", flush=True)
                            run.log("c4_press", key=key, frame=cam.frame.path.name)
                        cam.press("c4", allow={"c4"})
                    else:
                        press(cam, key, **shooting_word(cam, run, key, on_shooting))
                        # on the help popup a Down can go unanswered: the cursor stayed on Add to My
                        # Menu in 4 of 8 drives (S&Q, 2026-11-02), 0.3 s or 1.3 s after C4 alike.
                        # Down again while the lit entry still reads Add to My Menu, at most twice
                        for _ in range(2):
                            if key != "down" or cam.read().kind != "helppop" or \
                                    not re.search(r"my menu", highlighted(cam.frame.image, cam.frame.path), re.I):
                                break
                            print("   the popup's cursor did not move: Down again", flush=True)
                            press(cam, "down")
                    t = screen_text(cam, a.grip)
                    screens.append({"after": p, "frame": cam.frame.path.name, "kind": cam.read().kind, "text": t,
                                    **({"vouched": True} if vouched else {}),
                                    **({"on_shooting": True} if shooting else {}),
                                    **({"c4_allowed": True} if key in C4_OWNER_PRESSES else {})})
                    print(f"{p:32s} -> {cam.read().kind:9s} {cam.frame.path.name}  {t[:150]!r}", flush=True)
                if ok:
                    time.sleep(a.wait)
                    cam.refresh("after-presses")
                    t = screen_text(cam, a.grip)
                    screens.append({"after": "wait", "frame": cam.frame.path.name, "kind": cam.read().kind, "text": t})
                    print(f"{'(after ' + str(a.wait) + ' s)':32s} -> {cam.read().kind:9s} {cam.frame.path.name}  {t[:150]!r}",
                          flush=True)
            except Exception as e:
                print(f"error: {type(e).__name__}: {e}; cancelling", flush=True)
                ok = False
            # whatever ends the restore early (close giving up, a STOP while waiting, an upload refused) exits
            # EXIT_UNRESTORED (runner.restoring)
            with restoring("drive.py's restore"):
                close_for_restore(cam, link)
                try:
                    wait_for(hdmi, ("shooting",), "the settings download after the presses", link=link)
                except RuntimeError as e:
                    # the wait gave up: the restore is still tried, never skipped (decision 15); the download
                    # closes a menu itself, and ended() says so when the camera refuses it
                    print(f"   {e}; restoring all the same", flush=True)
                time.sleep(1)
                ending = session.ended(link, before, show=30)
                session.put_back(link, ending, before)          # first: a log that cannot be written skips nothing
                log.write(json.dumps({"path": a.path, "presses": a.press, "note": a.note, "completed": ok,
                                      **({"on_shooting": sorted(on_shooting)} if on_shooting else {}),
                                      **({"c4_allowed": c4_allowed} if c4_allowed else {}),
                                      "screens": screens, "before": before.name,
                                      "after": ending.after.name if ending.after else None,
                                      "changes": changes_of(ending.changes)}) + "\n")
                log.flush()
        restored = restore_checked(run, ending, before)
    finally:
        hdmi.close()
        log.close()
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


if __name__ == "__main__":
    main()
