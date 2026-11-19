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
Set., when the screen reads either and the lit text is not Camera Settings Reset, on a screen that asks or may ask by
its shape (safety.enter_refused, since 2026-11-14: a notice, a screen of no known kind, one whose text reads nothing, a
question mark above its footer, a carousel that asks), and on a screen that reads like a confirmation
(safety.confirmation_refused: confirmation, its words run together too). The ways past are named and narrow: the owner
route (--owner --confirm, the row's name typed at the terminal) lifts both for its step or armed press, never the rest;
--confirm "SCREEN TEXT" without --owner lifts the shape check, once, for an Enter on the screen whose whole text it
gives (runner.confirm_phrase_or_exit, runner.screen_named), never the confirmation words, so a format, a delete or a
reset goes only by the owner route; --info-ok "ROW=PHRASE", ROW a --path label, takes the OK of the plain notice it
names (proving.screens.notice_refused: OK alone, no question, the phrase its whole text). The camera makes the shape
check itself on every Enter (camkit.live.LiveCamera.confirm_refused), on the screen looked at again just before the
press, lifted only for a press drive.py allowed as an owner row's (live.press's confirm, LiveCamera.permit), and given
the consent or the notice named. Right or Enter onto a lit row on the never-open list is refused unless --allow names
it, and Right on a menu page whose lit row cannot be read is refused.
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
is lifted: the never-open list, Initialize, Reset Network Set., the confirmation check and the shape check (since
2026-11-14 the MR Memory slots, read as no known kind, take a vouched Enter only with --confirm naming their screen)
and C4 stay as they are (press_decision).
"help" presses C4 (the trash button) for the In-Camera Guide, only on a menu or option screen whose
footer draws the help button; Enter on its popup only on "In-Camera Guide", never Add to My Menu.
--grip up|down (the camera held vertically, 2026-11-02): dialogs opened from the menu turn on screen while
the menu pages stay level, so each screen is read both as it is and turned upright (as kit/provers/orient_run.py
does), and a press's regex may match either.
"c4set" presses C4 on Focus Area's screen with Custom 1-3 lit, where the button reads SET and opens the
custom box's size editor. Nowhere else, never on the shooting screen or in Playback, where C4 deletes; in the editor
itself, a screen of no known kind, the link refuses it (its Reset goes from kit/provers/boxsize_run.py alone, decision 7).
"c4reset" presses C4 on a Creative Look's panel whose footer reads Reset.
Both are go-aheads an owner gives for their own body (the a1 II's owner gave them on 2026-11-02 and 2026-11-03), never a
default: a run sends one only when --c4-press names it (--c4-press c4set, --c4-press c4reset), the owner's word for this
run, and a --press using one without it is refused before anything connects; the word is said in the console, the
run's events.jsonl and drive.jsonl, as --on-shooting's is. "help" (guarded Help) needs no word: AGENTS.md allows it.
Rows on the never-open list are refused unless named with --allow; no --allow opens anything on the cards,
Initialize, Reset Network Set., a credentials screen or the camera's identity, a connection or its region, nor a Wi-Fi
or Bluetooth setting or an address screen (decision 8: safety.allow_refused, judged on every --allow and every --path
label before anything connects, and safety.never_lifted on the camera; --network below). A path "Picture Profile", "PP3", ... opens that profile's own panel (opening it makes it the Picture
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
--network makes the run a look lap (docs/decisions/0024): a never-open row opens to look at, no decision naming it,
but what safety.look_lap_refused refuses: OWNER_NEVER's rows and the Screen Reader, a row whose opening acts (the
owner's own run, each time) and a format, delete or reset this body's records have not shown opened (the owner's own run
first): a --path naming one stops the run before anything connects; a --path label it opens needs no --allow. Such a
row is looked at as a row a decision opened with no option named, the frames of what the owner route blanks saved black
from its opening (safety.look_blank), and the
camera's own check judges the same. --network also opens the Wi-Fi and Bluetooth rows, address screens and identity
rows a dated owner decision in the reviewed scope names ({"lifts": "network", "date", "rows", "why"}:
runner.network_decided_or_exit, docs/decisions/0008), with the options it names; without --network they stay closed,
and no --allow opens one. A decision naming credentials, an identity row that stays closed, an action or the serial
number stops the run before anything connects. A --network run asks local readers only (camkit.vlm.LOCAL_ONLY) and marks its
folder so (runner.log_network_decided) for the tools that read its frames later. Once a press has opened such a row it
is looked at only (inside_refused, safety.look_refused) until the screen read right after a MENU, or an Enter on a
named option, is the shooting screen or the page it was opened from with its lit bar on the row itself (network_left;
never on a screen's kind alone, never on a later press): up, down and MENU go out, Enter only on an option the
decision names ("options": {"<row>": ["<option>"]}), never Right, Left, a dial or C4;
a screen there that names identity or credentials (safety.identity_screen: a pairing screen, a connecting notice) gets
MENU alone. From the run's start to its end (--owner's too, but the owner row's own screens where its decision logs
values) no screen's text is printed or kept: every screen is shown and kept as safety.kept_screen keeps it, its row
labels and field names, a list's option names where the definition gives them for its row (never which one is lit), a
notice as safety.notice_kept keeps it, and the count of lines withheld; the shooting screen as its kind alone; and the
quoted texts of a refusal or an error are withheld. The run's folder is owner-only (camkit.runs: folders 0700, files
0600, on POSIX), checked at its end. An address screen (Display
Wi-Fi Info., Display Wired LAN Info., Disp Device Address: safety.address_screen) opens only here, only as the last
label of --path and only where a decision names it: the run prints and keeps every screen as its field names alone
(safety.address_fields: never an OCR text, in the console, drive.jsonl or the run's events), asks no reader once it is
open (camkit.vlm.HELD), and once a press has opened a row, whatever the screen reads as, no key but MENU goes out.
A row's own screen read as the shooting screen before any MENU or closing Enter is judged as no known kind (MENU alone,
field names only), and no later frame read as the shooting screen ends the row unless the camera's own picture says
so too (network_left). The row labels a withheld screen keeps are the definition's and the page model's, never an
option a row path names, and no line that is a value they know is kept (runner.known_labels, known_values); a lit row
read with its icon glued on ("LANIP Address Setting") opens as the decided row only where the page model's row holds
the decided label in another reader's reading (runner.network_readings, safety.lifted_readings).
--owner opens the one row a dated owner decision in the reviewed scope names ({"lifts": "owner", "date", "rows", "why"}:
runner.owner_decided_or_exit, docs/decisions/0004, 0005, 0008 and 0009), as the last label of --path, one row per run:
credentials, the serial number, a closed identity row, an action, a card's Format or Delete; never a firmware update,
anything that loads a file or settings, Initialize, nor a row of sound, light or motion or the Screen Reader. An
action's or a card's row is named by its path in the decision ("Tab > Group > Row [> Row ...]"), and so is any row whose
label the kit knows in more than one place; the run goes to it in that tab and group (crawl_run.go_to's place) and opens
nothing unless the page shown reads them (place_refused); a deeper row is walked to with each parent's lit bar read before
its Right and the title of the page it opens read after it, a page the Right left in its position refused (owner_walk),
the last read again at the opening (opening_place_refused); between the walk and the opening only Up and Down go out,
and from then on no Right or Enter that is not the owner row's opening or a press inside it (LiveCamera.owner_only
beside), --confirm covering only a press judged a step or the armed press. Before any --owner run given --confirm connects (safety.asks_person), the person at
the terminal types the row's name, its whole place printed (typed_word: a real TTY, no flag or environment variable;
"unattended": true in the decision waives it, said beside "confirm" or a never-choose row's "options" with
"link_loss"). It stops a careless agent, not a determined one: a program driving a pseudo-terminal can answer it, so
the owner types the answer themselves. The row opens with Right alone, from a menu page,
to look: up, down and MENU, and Enter only as below (owner_press_decision, and camkit.live.LiveCamera's own check on its own
reading). An action or a card row the kit has not seen open a list or a question at that very place
(safety.opens_to_look: Format and Delete are not among them), and every row that acts as soon as it opens (WPS Push,
Pairing, Create New Folder...), opens only as the armed last press of a run given --confirm, the row under "confirm".
An option the decision names ("options") is chosen where its choice keeps the link. Inside an action any Enter may be
the final one: a step goes before the last press only where the decision marks it seen ("steps_seen"), the screen reads
as no question and shows no dialog's two buttons (safety.confirm_pair), and another Enter follows; any other step is the
armed last press ("final"), and any other Enter there the action's confirmation, armed once on a dialog or a notice
whose lit text is a confirm button and whose whole text is that action's confirmation (safety.arm_refused); a
never-choose option ("link_loss": true) is armed too. Steps and armed presses need --confirm, armed presses the run's
last press. The camera's own check presses each only when this run allowed that very press (LiveCamera.permit). Before
a press that may drop the link (Reset Network Set., SSID/PW Reset, a never-choose option, an opening that may change
the network: safety.loses_link) the camera's runs/<model>_fw<fw>/RESTORE_BY_HAND.json is written, naming the start file
(intend_by_hand; no link opens while it is there until kit/tools/upload_check.py has put that file back). A press
refused before it went (safety.Refused, a STOP, or camkit.link.CameraRefused, answered "not accepted") takes it away
and ends the run as any refusal does, closing and restoring. Any other failure keeps it: nothing more is pressed, no
remote restore is tried, and the run exits EXIT_RESTORE_BY_HAND (5). Once the press went the screen is read once
(after_armed): a read that fails, a black frame, a kind the kit does not read or no text, the same exit 5; the row's
own question (safety.own_question) is cancelled with MENU alone, never Enter, at most three times (cancel_question),
the start file restored, the marker taken away once the restore checks out, drive.jsonl saying "question shown,
cancelled" with the question's frame, and the run exits EXIT_NOT_CONFIRMED (6): nothing was confirmed; a question MENU
does not clear stays for a person, exit 5; any other screen, the link still answering, gets the MENU-only close and the
remote restore, the marker taken away only when that restore checks out, else exit 5. Without "values": "logged" a
credentials or closed identity row is blanked, and the serial number screen always (safety.blanked):
every frame from its opening is written black by the eyes (camkit.frames), no OCR text of it is kept, no reader is
asked, MENU alone; an action's screens are shown and kept as their field names and row labels. With it the screens'
text goes to drive.jsonl only, the console showing their field names and "(values in drive.jsonl)". A --owner run asks
local readers only, and its folder is marked so no batch tool asks any reader about its frames
(camkit.vlm.NO_READER_MARKER). Nothing is typed: a keyboard or an entry screen takes MENU alone.
A run (never an --owner one) that opens a --path's last row this camera has not been seen to open (camkit.first_open)
makes that row's first open: only with the owner's blank-cards statement (camkit.statements), only with --press right
alone and every row above it seen, and its Right goes as an armed press that may drop the link does (RESTORE_BY_HAND
first, one read after it, MENU and the remote restore); the screen that read finds is one the kit reads where its kind
is one of safety.FIRST_OPEN_KINDS, the armed press's kinds and the other option screens MENU leaves (a slider, number
fields, a table...), for a first open alone (a screen of no known kind, a black frame or no text still keeps the marker,
exit 5); the marker goes only when the start file comes back checked with no record differing, else the run exits
EXIT_RESTORE_BY_HAND (first_open_or_exit). The run's look (camkit.coverage.drive_look) is an open only where nothing but
up, down and MENU followed the opening press: a run that pressed anything else inside a seen row is a choice, which a
record it changed leaves seen. The lit bar an opening press
meets is judged by lit_refused: on the first press after the page scan went to a one-label --path's row, a bar read
with the row's icon as a letter or two before its label ("S Exposure Comp. +0.0"), or its label ending in a stop
before a value ("Exposure Comp. +0.0"), is that row where the page model keeps that very reading of it and the value
is one the kit knows for it (icon_reading). A camera other than the one the kit works on stops the run before anything
is pressed.
Results: runs/<model>_fw<fw>/<run>/drive.jsonl; frames and downloads in the same run folder. The settings are downloaded before
and after; the diff is kept with the result, and if anything changed the start file is uploaded and the restore
checked (docs/decisions/0015: every run ends restoring its start file). On an address, --network or --owner run the
records that differ are said and kept by key and count alone, never a value (runner.values_withheld, changes_kept),
unless the owner row's decision logs values. A run whose first --path label the scan does not reach (find_position,
crawl_run.go_to) sends none of its presses, says the label as it was given (the run's own argument, on every run),
restores its start file and, once that checks out, exits EXIT_INCOMPLETE (8; kit/exit_status.py), so a chain or an
agent can tell it from a run that did its presses. A run whose restore does not finish (EXIT_UNRESTORED, 4) keeps a
result line in drive.jsonl saying so, with no screen (unfinished_line).
"""
import argparse
import contextlib
import functools
import json
import re
import sys
import time
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import match, ocr, safety, screen  # noqa: E402
from camkit import coverage, first_open  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import CameraRefused, Link, StopRequested  # noqa: E402
from camkit.live import (WITHHELD_ROW, LiveCamera, black, body_of, info_ok_hint, info_ok_text, lit_found,  # noqa: E402
                         lit_text, lone_of, look_row, open_refused, osd_kind, press, submenu_labels, text_of)
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run, clear_restore_by_hand, mark_restore_by_hand  # noqa: E402
from camkit.screen import same_position, same_state  # noqa: E402
from camkit.session import wait_for  # noqa: E402
from crawl_run import find_position, go_to, group_shown, tab_shown  # noqa: E402
from prove_run import enter_any  # noqa: E402
from runner import (EXIT_INCOMPLETE, EXIT_NOT_CONFIRMED, EXIT_RESTORE_BY_HAND, EXIT_UNRESTORED, LOOK_LAP,  # noqa: E402
                    add_info_ok_argument, add_network_argument, add_owner_argument, add_scan_argument,
                    cards_statement_refused, changes_kept, close_for_restore, confirm_phrase_or_exit, defined_values,
                    definition, end_session, info_ok_or_exit, row_labels,
                    known_labels, known_values, label_readings, load_scan, log_network_decided, log_owner_decided,
                    menu_from_shooting,
                    network_decided_or_exit, network_readings, network_values, owner_decided_or_exit,
                    restore_checked, restoring, row_readings, row_values, screen_named, values_withheld, wait_shooting)


class NotReached(RuntimeError):
    """The --path's first label was not reached by the scan (find_position, go_to): the run cancels, restores and exits
    EXIT_INCOMPLETE. Its message names the label as the run was given it (`label`, the run's own argument, never a text
    read off the screen), shown on every run, a --network or --owner one too (2026-11-14: "could not reach
    '(withheld)'" withheld the very row the decision names)."""

    def __init__(self, label: str):
        super().__init__(f"could not reach {label!r} by the scan")
        self.label = label


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
# and SSID/PW Reset, which wipes the camera's own network (2026-11-13): safety.LINK_WIPING_ENTER, which camkit.live's own
# check reads too
NEVER_ENTER = safety.LINK_WIPING_ENTER
# the one reset decision 5 allows, which shares its screen with Initialize (Setting Reset's two rows)
CAMERA_SETTINGS_RESET = safety.CAMERA_SETTINGS_RESET
ENTERS, RIGHTS = ("enter", "ms_enter"), ("right", "ms_right")
# screens where Right opens the lit row: there the row must be read before it is opened; boxed options alone
# ("buttons", read as no known kind until 2026-11-16) as an unknown screen
ROW_KINDS = ("menu", "submenu", "tiles", "shooting", "unknown", "buttons")
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
    them; a dial turn is named by its dial), and on the camera's playback view (kind "playback", camkit.live's reading)
    none but MENU, named or not (decision 21)."""
    name = press_name(key)
    if kind == "playback" and name not in safety.SHOOTING_FREE:
        return ("the screen is the camera's playback view (it says it is in Playback), not the shooting screen: no key "
                "but MENU goes out there, --on-shooting or not")
    if kind != "shooting" or name in safety.SHOOTING_FREE or name in on_shooting:
        return ""
    return (f"the screen is the shooting screen, where {name!r} does what the body makes of it: only with the owner's "
            f"word, --on-shooting {name}")


# Whether the Initialize, Reset Network Set. or SSID/PW Reset a screen reads is the very action this run armed as its
# last press: only then does press_refused let Enter go on that screen (safety.armed_wiping, camkit.live's too)
armed_wiping = safety.armed_wiping


def press_refused(key: str, lit: str, text: str, kind: str, confirm: bool = False, allow=(),
                  vouched: bool = False, on_shooting=(), network=frozenset(), screens: bool = False,
                  values=None, readings=None, owner=None, armed_row: str = "", labels=None, body=None,
                  consent: str = "", notice_way: str = "", lone=None, look: bool = False, row=None) -> str:
    """Why drive.py may not send this press, or "" when it may. Fails closed: a lit text that cannot be read is
    no permission (decisions 5 and 9). lit: the text in the orange cursor (highlighted); text: the whole screen's.
    `confirm`, the owner route's (--owner --confirm, for a press its gates judged a step or the armed press), allows
    Enter on a confirmation, never on Initialize or Reset Network Set. The key is judged as canonical_key folds it
    (" enter" is Enter), and one that is no key is refused.
    Enter is refused, since 2026-11-14, on a screen that asks or may ask by its shape (safety.enter_refused, as the
    camera's own check judges it: a notice, a screen of no known kind, one whose text reads nothing, a question mark
    above its footer, `body` when given, else in the whole text, a carousel that asks), unless `confirm`; or `consent`,
    named for this one screen (a prover's --allow for its own row, kit/provers/memreg_run.py's slot screen; --confirm
    "SCREEN TEXT" without --owner, once): the shape refuses nothing, the confirmation check still does; or, on a notice,
    `notice_way` (the notice has just refused MENU; the notice --info-ok names) where `lone` (safety.lone_ok's verdict)
    says its OK is its only button. A vouch (enter!:regex) lifts the unreadable lit text alone, never this: the MR
    Memory slots, read as no known kind, need --confirm naming them.
    vouched (enter!:regex): the operator vouches for Enter, so an unreadable lit text alone does not refuse it, on a
    screen that is not in VOUCH_REFUSED, whose whole text reads something (a regex such as ".*" matches a blank
    screen too, and a blank text gives screen_refused nothing to judge) and names nothing never-open
    (safety.screen_refused).
    on_shooting (--on-shooting, keys as canonical_input gives them): on a screen read as the shooting screen a key named
    there is judged by that naming (decision 21): it has no row to open, so the refusals of a lit text that cannot be
    read, and the lit row's never-open check, are not made; Enter still meets the Initialize and confirmation checks.
    On every other screen, "unknown" among them, nothing changes.
    network, screens, values, readings, labels (--network): the Wi-Fi and Bluetooth rows a dated owner decision opens,
    whether an address screen among them may, the values known for each, the page model's readings of each and every
    label the kit knows (live.open_refused); --allow never lifts those rows. look, row: a look lap's (--network,
    docs/decisions/0024: live.open_refused), row the --path's last row when this press opens it (live.bar_is_row).
    owner (--owner): the one row an owner decision opens for this run ({label: info}): a lit text that is that row, of
    its class (safety.owner_lifted_row), passes the never-open check, the press that opens it and an action's own
    button among them ("Delete" on Delete's question); whether the press may go is owner_press_decision's and
    owner_open_decision's. armed_row: the row whose confirmation this run armed as its last press: the screen's
    Initialize or Reset Network Set. lets Enter go only when it is that very action (armed_wiping). The confirmation
    check (--confirm) is made on the whole text as read, armed or not, and the lit text is judged as ever."""
    canon = canonical_key(key)
    if canon is None:
        return f"{key!r} is not a key drive.py sends"
    key, lit = canon, (lit or "").strip()
    named = kind == "shooting" and key in on_shooting      # no row on the shooting screen: the naming judges it
    if key in ENTERS and not named:
        if not lit and not vouched:
            return ("nothing lit can be read, so the button under the cursor is unknown: where you know what Enter does "
                    "on this screen, --press 'enter!:REGEX' vouches for it")
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
        if m and not CAMERA_SETTINGS_RESET.search(lit) and not armed_wiping(armed_row, m.group(0)):
            return f"the screen reads {m.group(0)!r} and the lit text {lit!r} is not Camera Settings Reset"
        said = safety.confirmation_refused(text)       # its words run together too ("Formatthe memory card?")
        if said and not confirm:
            return f"{said} on {(text or '')[:120]!r}"
        # what the screen asks, by its shape: the camera judges it too (camkit.live.LiveCamera.confirm_refused)
        asked = safety.enter_refused(kind, text, lit, body, notice_way, lone, key=key)
        if asked and not confirm and not (consent and str(text or "").strip()):
            return f"{asked}: only with --confirm naming this screen by its whole text (once), or by the owner route"
    if key in RIGHTS and not lit and kind in ROW_KINDS and not named:
        return f"nothing lit can be read on a {kind!r} screen, so the row Right would open is unknown"
    if key in ENTERS + RIGHTS and lit and not named:
        why = open_refused(lit, allow, network, screens, values, readings, labels, look, row)
        if why and owner and safety.owner_lifted_row(lit, owner, values) is not None:
            return ""
        return why
    return ""


def press_decision(p: str, key: str, lit: str, text: str, kind: str, confirm: bool = False, allow=(),
                   on_shooting=(), network=frozenset(), screens: bool = False, values=None, readings=None, owner=None,
                   armed_row: str = "", labels=None, body=None, consent: str = "", notice_way: str = "",
                   lone=None, look: bool = False, row=None) -> tuple:
    """(why the press is refused or "", whether it goes as vouched) for the --press `p` whose key is `key`, on a screen
    whose lit text is `lit`, whole text `text` and kind `kind`, as main() sends it: a press written enter!:regex is
    vouched for (press_refused's vouched) only when it is Enter, and goes as vouched only when nothing lit could be
    read and nothing refuses it. on_shooting: the keys --on-shooting named; network, screens, values, readings:
    --network's; owner, armed_row: --owner's; body, consent, notice_way, lone: the text above the footer, a consent named
    for this screen (a prover's --allow for its own row; --confirm "SCREEN TEXT") and a notice's way past with its lone
    OK verdict (press_refused); look, row: a look lap's (press_refused)."""
    vouched = vouched_press(p) and key in ENTERS and not (kind == "shooting" and key in on_shooting)    # named instead
    why = press_refused(key, lit, text, kind, confirm, allow, vouched, on_shooting, network=network, screens=screens,
                        values=values, readings=readings, owner=owner, armed_row=armed_row, labels=labels, body=body,
                        consent=consent, notice_way=notice_way, lone=lone, look=look, row=row)
    return why, bool(vouched and not why and not (lit or "").strip())


def enter_ways(cam, key: str, phrase, named: dict, words: bool = True) -> tuple:
    """(consent, notice row, lone verdict) for the press `key` about to be judged, the ways past the shape check a run
    without --owner names (2026-11-14): `phrase`, --confirm's words (runner.confirm_phrase_or_exit), gives the consent
    "--confirm '...'" where the screen on show is the one it names (runner.screen_named: every OCR line, its buttons too),
    for press_refused's consent and the camera's answer_once, which keep the confirmation words; `named`, --info-ok's
    {row: phrase}, gives the row whose notice the screen is (proving.screens.notice_refused) and that notice's lone OK
    verdict (camkit.live.lone_of), for press_refused's notice_way and the camera's notice_ok. ("", "", None) for any key
    but Enter, and where nothing names the screen."""
    if key not in ENTERS:
        return "", "", None
    consent = ""
    if phrase:
        try:
            lines = ocr.read([cam.frame.path])[cam.frame.path]
        except Exception:
            lines = None
        if lines is not None and not screen_named(phrase, lines):
            consent = f"--confirm {phrase!r}"
    notice_row, lone = "", None
    if named and cam.read().kind == "notice":
        from proving.screens import notice_refused
        notice_row = next((row for row, said in named.items() if not notice_refused(cam, said, words)), "")
        if notice_row:
            lone = lone_of(cam.frame.image, cam.frame.path)
    return consent, notice_row, lone


ARMED = ("confirm", "choose", "open", "final")     # the owner presses armed as the run's last press: one per run


def owner_open_decision(key: str, lit: str, kind: str, label: str, info: dict, last: bool, confirm: bool,
                        opened_before: bool) -> tuple:
    """(why drive.py may not send `key` onto the owner row `label` lit (`lit`), or "", what it is: "look", or "open"
    for a row that acts on opening): Right alone, never Enter, the multi-selector or a look-alike; once per run
    (opened_before); from a menu page alone (`kind`, safety.ROW_PAGES: where the camera judges it too); a row that acts
    on opening (WPS Push, Pairing, Create New Folder...) only under "confirm", in a run
    given --confirm (`confirm`), as its last press (`last`), safety.arm_refused passing on this reading."""
    if safety.name_refused(key) or key != "right":
        return f"the owner decision opens {label!r} with Right alone, never {key!r} (docs/decisions/0008)", ""
    if opened_before:
        return f"one owner row per run, opened once: {label!r} was opened already (docs/decisions/0008)", ""
    if kind not in safety.ROW_PAGES:
        # the camera judges an opening on a menu page alone (LiveCamera): opened anywhere else, its own lock would not
        # hold the row
        return f"the owner row {label!r} is opened from a menu page, not a {kind!r} screen (docs/decisions/0008)", ""
    if not info.get("acts_on_open"):
        return "", "look"
    if not confirm:
        return f"{label!r} acts as soon as it opens: only in a run given --confirm (docs/decisions/0008)", ""
    if not last:
        return f"{label!r} acts as soon as it opens: only as the last press of the run (docs/decisions/0008)", ""
    why = safety.arm_refused(label, info.get("class"), "open", kind, lit, "", info.get("confirm", False),
                             info.get("link_loss", False), place=info.get("path"))
    return why, ("" if why else "open")


def owner_press_decision(key: str, inside: dict, info: dict, lit: str, text: str, kind: str, last: bool,
                         confirm: bool, later_enter: bool = False) -> tuple:
    """(why drive.py may not send `key` inside the owner row open (`inside`), or "", what it is: "" for up, down or
    MENU, else safety.owner_enter's "option", "step", "final", "confirm" or "choose"), whatever the camera checks after
    it. Only up, down, MENU and Enter, each in its own spelling (safety.OWNER_KEYS_INSIDE: never ms_enter, Right, Left,
    a dial or C4); after the armed press, or on a screen that takes MENU alone, MENU alone. Enter is read off the screen
    now: inside an action or a card row any Enter may be the final one: a step goes before the last press only where
    the decision marks it seen safe and the screen reads as no question (safety.owner_enter) and an Enter follows it in
    the run (`later_enter`); any other named step is "final", and an Enter whose lit text is no named step the
    confirmation. A step needs --confirm (`confirm`); a final step, a confirmation and a never-choose option need
    --confirm and the run's last press (`last`), and safety.arm_refused passing on this reading."""
    row, cls = inside["row"], inside.get("class")
    name = press_name(key)
    if safety.name_refused(key) or name not in safety.OWNER_KEYS_INSIDE:
        return (f"{key!r} never goes out inside {row!r}, a row an owner decision opened: only up, down, MENU and Enter "
                "(docs/decisions/0008)"), ""
    if name == "menu":
        return "", ""
    if inside.get("done"):
        return "the armed press of the run has gone: no key but MENU (docs/decisions/0008)", ""
    if inside.get("identity") or inside.get("address"):
        return f"a screen that takes MENU alone is open inside {row!r}: no key but MENU (docs/decisions/0008)", ""
    if name != "enter":
        return "", ""
    why, what = safety.owner_enter(row, cls, kind, lit, text, info.get("options") or (), info.get("steps_seen") or ())
    if why or what == "option":
        return why, ("" if why else what)
    if what == "step" and not later_enter:
        what = "final"              # no Enter after it in the run: nothing would confirm it, so it may be the final one
    if not confirm:
        return f"inside {row!r} this Enter is a {what}: only in a run given --confirm (docs/decisions/0008)", ""
    if what in ARMED and not last:
        return f"inside {row!r} this Enter is a {what}: only as the last press of the run (docs/decisions/0008)", ""
    why = safety.arm_refused(row, cls, what, kind, lit, text, info.get("confirm", False), info.get("link_loss", False))
    return why, ("" if why else what)


def place_refused(text: str, tab: str, group: str) -> str:
    """Why the menu page shown, its whole text as read (`text`: its breadcrumb leads it), is not the owner row's own
    tab and group, or "": the tab it names first (crawl_run.tab_shown) is `tab`, and its breadcrumb names `group`
    (crawl_run.group_shown). A breadcrumb that cannot be read refuses as one that differs (2026-11-13, a review: go_to
    goes to the first row of that label, wherever it is)."""
    if not (text or "").strip():
        return "the page's breadcrumb cannot be read, so its tab and group are not known"
    shown = tab_shown(text)
    if shown is None or safety.plain(shown) != safety.plain(tab):
        return f"the page shows the tab {shown!r}, not {tab!r}"
    if group_shown(text, [group]) != 0:
        return f"the page's breadcrumb does not name the group {group!r}"
    return ""


def reads_row(lit: str, label: str) -> bool:
    """Whether the lit bar's text is the row `label`: compared whole (plain), the label alone or followed by what is no
    letter or digit of a longer word (a value after it)."""
    want, seen = safety.plain(label or ""), safety.plain(lit or "")
    return bool(want) and seen.startswith(want) and not seen[len(want):len(want) + 1].isalnum()


def title_refused(kind: str, text: str, parent: str, lead=()) -> str:
    """Why the screen (its kind and whole text as read) is not the submenu page the row `parent` opened, or "": a submenu
    page whose text begins with the parent's label as its title, alone or after a breadcrumb of the labels above it
    (`lead`: the row's tab, its group and the parents above, whole or their first parts, "Tab > Group > Parent" or
    "Tab > Group Parent"). The breadcrumb and the title run together with a space only right after the tab or the
    group; after a parent, only " > " (a fifth review: "Tab > Group > Parent Child ..." is the parent's own page with
    its row Child in it, never Child's page). A text that cannot be read refuses (2026-11-14, a fourth review: the place
    of a row deeper than its top-level row was not checked)."""
    if kind != "submenu":
        return f"the screen reads as {kind!r}, not the submenu {parent!r} opens"
    seen, want = safety.plain(text or ""), safety.plain(parent or "")
    if not seen:
        return f"the title of the page {parent!r} opens cannot be read"
    crumb = [safety.plain(x) for x in lead if safety.plain(x)]
    heads = [want] + [" > ".join(crumb[:k]) + sep + want for k in range(len(crumb), 0, -1)
                      for sep in ((" > ", " ") if k <= 2 else (" > ",))]
    if want and any(seen.startswith(h) and not seen[len(h):len(h) + 1].isalnum() for h in heads):
        return ""
    return f"the page's title does not read {parent!r}"


def owner_walk(cam, path: list, grip, place=(), tries: int = 40) -> str:
    """The walk from the owner row's top-level row (lit on the page its tab and group were read on) to the owner row's
    own page, for a --path deeper than one label, or why it is refused (""): for each parent, its lit bar must read it
    before its Right, the page that Right opens must be a submenu whose title reads it, after the breadcrumb of the
    decision's tab and group (`place`) and the parents above (title_refused), and Down alone
    then lights the next label (at most `tries` presses, never past the first lit row seen again). A page after a Right
    in the same position as the page before it (same_position) refuses: the Right was ignored or drawn late, and the
    page shown is still the parent's own (a fifth review). Whatever cannot be read refuses (2026-11-14, a fourth
    review)."""
    for i, parent in enumerate(path[:-1]):
        lit = highlighted(cam.frame.image, cam.frame.path)
        if not reads_row(lit, parent):
            return f"the lit row reads {lit.strip()!r}, not {parent!r}, so it is not opened"
        before = cam.read()
        press(cam, "right")
        try:
            stayed = same_position(cam.read(), before)
        except Exception:               # two screens that cannot be compared: nothing tells that the Right was taken
            stayed = True
        if stayed:
            return f"the page after Right on {parent!r} is in the same position as before it: the Right was not taken"
        why = title_refused(cam.read().kind, screen_text(cam, grip), parent, [*place[:2], *path[:i]])
        if why:
            return why
        nxt, first = path[i + 1], None
        for _ in range(tries):
            lit = highlighted(cam.frame.image, cam.frame.path)
            if reads_row(lit, nxt):
                break
            if not lit.strip() or lit == first:
                return f"no row {nxt!r} lit on the page {parent!r} opens"
            first = first or lit
            press(cam, "down")
        else:
            return f"no row {nxt!r} lit on the page {parent!r} opens"
    return ""


def opening_place_refused(kind: str, text: str, path: list, place: list) -> str:
    """Why the screen an owner row's opening press is made on is not the row's own place, or "": for a --path of one
    label, the page's breadcrumb reads the decision's tab and group (place_refused); for a deeper one, the page is the
    submenu the row's parent opened, its title reading that parent (title_refused). The parents above were read on the
    walk (owner_walk), and between it and the opening only Up and Down went out."""
    if len(path) == 1:
        return place_refused(text, *place[:2])
    return title_refused(kind, text, path[-2], [*place[:2], *path[:-2]])


def typed_word(label: str, place: list, what: str, camera: str, read=None, tty=None) -> str:
    """Why the person at the terminal did not let the run make its armed press in the owner row `label`, or "": the run
    prints the row's whole place, what the press does and the camera, and the person types the row's last label; the
    prompt asks for the row's name and never prints it as the answer to type. Only a real terminal answers (`tty`,
    sys.stdin.isatty() unless given); no flag or environment variable does (2026-11-14, a fourth review). It stops a
    careless agent, not a determined one: a program driving a pseudo-terminal can answer it, so the owner types the
    answer themselves (a fifth review). `read`: input, unless given. The terminal is read as the owner's statements
    are (camkit.statements.typed)."""
    from camkit.statements import typed
    got = typed(f"the owner row {' > '.join(place)!r} on the camera {camera}: the run's last press may {what}. The owner "
                "types the row's name, the last label of its place, to go on (anything else stops the run):",
                read or input, tty)
    if got is None:
        return ("its armed press needs the person at a terminal to type the row's name, and this run has no terminal "
                "(standard input is no TTY): nothing was sent. Run it in a terminal, or the owner writes "
                "\"unattended\": true in the decision (docs/decisions/0004 and 0005)")
    if safety.plain(got) != safety.plain(label):
        return f"the person typed {got.strip()!r}, not {label!r}: nothing was sent"
    return ""


def armed_words(info: dict) -> str:
    """What the last press of a confirming run in the owner row of `info` may do, in words, for the terminal question
    (every such run asks it, safety.asks_person): a reset that wipes the link; a card's Format or Delete; a row that
    writes to a card (safety.writes_card) or registers at once (safety.registers), named for what nothing puts back
    (a fifth review: "start what the row does" said nothing of the card); an opening that acts; an action's
    confirmation; a never-choose option, which may drop the link; another option; else a look."""
    label = info.get("label")
    if safety.link_wiping(label):
        return "reset the camera's network setup and drop the link to it"
    if info.get("class") == safety.LIFT_CARDS:
        return "format or delete what is on a card, which nothing puts back"
    if safety.writes_card(label):
        return "write to a card, which nothing puts back"
    if safety.registers(label):
        return "register at once; no settings file puts it back"
    if info.get("acts_on_open"):
        return "start what the row does as soon as it opens" + (", and drop the link to the camera"
                                                                if safety.link_risk_open(label) else "")
    if info.get("class") in safety.ACTION_CLASSES:
        return "confirm the row's action"
    chosen = ", ".join(info.get("options") or ())
    if chosen and safety.never_choose(label):
        return f"choose {chosen}, which may drop the link to the camera"
    if chosen:
        return f"choose {chosen}"
    return "only open the row, to look: nothing in it is chosen or confirmed"


OPENERS = ENTERS + RIGHTS          # a --press that opens the lit row: the --path's last row, on its page
ROW_PAGES_OPENED = ("menu", "submenu")      # the pages whose lit row an opening press opens (lit_refused)


def lit_refused(lit: str, depth, path: list, seen, known=(), decided=None, values=None, gone_to=None) -> tuple:
    """(why the opening press may not open the lit row of the menu page shown, or "", the row's path) for a run that is
    no --owner one. One rule: the row is the longest label the lit text starts with, as a whole word, among those the
    kit knows (`known`: the definition's, the page model's, the --path's last row and the page's own labels read live,
    shown_labels) or of a rows seen there (camkit.first_open.Seen.lit_row); words the lit text runs on with past that
    label must be a value of the row the kit knows (`values`: {label: values}, runner.row_values: the definition's and
    the page model's, compared plain), else the bar may be a longer row's and nothing opens: a seen row showing a value
    the kit does not know yet (a body with no definition) is named in --path instead. Where that rule takes the bar for
    no row, or for the --path's own row with words past its label that are no value of it, and the run went by the page
    scan to the --path's row at this level and has pressed nothing since (`gone_to`: the page model's row go_to reached
    and the names other rows go by, an ordinary run's alone: icon_reading), the lit bar is that row where it starts
    with a reading the page model keeps of it, its label itself or that label with the row's icon read as a letter or two
    before it ("S Exposure Comp. +0.0"), both with their last stop kept (stop_kept: plain leaves out the stop of
    "Exposure Comp.", so "Exposure Comp. +0.0" ran on with ". +0.0"), and the words past that reading are none or a
    value of the row as above; or, where the page model saw the row drawn with an icon, it is that row behind any icon
    read in front as a stray mark or a letter or two (icon_behind: camkit.match.ICON's rule), also where that rule took
    the icon itself for a short row the kit knows ("R Peaking Color White" read as Color Depth's "R": in_icon); else
    that rule's refusal stands. The --path's own last row (`depth` its labels above, the page enter_any walked to) is then judged by
    first_open_or_exit; any other opens only where this camera has been seen to open it, so walking within a seen parent
    to a seen row stays plain. On a submenu page (no page model), where that rule takes the bar for no row, for the
    --path's own last row with words past it that are no value of it, or for a row named by a reading of the lit row
    itself, the bar is that last row where the page as read live on the bar's own frame ties it so (`known` holds that
    reading, a SubmenuBar, shown_labels's; the page is the --path's last row's own, `depth` its labels above:
    submenu_tied); else the refusal stands. Where the page shown cannot be placed (`depth` None, after a MENU or a Left on a menu
    page) nothing opens. `decided`: the row a network decision opens that the lit bar reads as (safety.network_lifted_
    row: its icon glued on and its value judged there), which is then the row."""
    named = "name it in --path, so its first open runs under the link-loss procedure"
    if depth is None:
        return f"the menu page shown is not one the run can place, so the lit row cannot be judged: {named}", None
    row = (*depth, decided) if decided else seen.lit_row(depth, lit, {*known, path[-1]})
    why = f"the lit row reads {lit.strip()!r}, a row this camera has not been seen to open: {named}" if row is None else ""
    if row is not None and not decided:
        label = first_open.key(row)[-1]
        rest = safety.plain(lit)[len(label):].strip()
        if rest and rest not in {safety.plain(v) for v in (values or {}).get(label, ())}:
            why = (f"the lit row reads {lit.strip()!r}, which runs on past the row {row[-1]!r} with words that are no "
                   f"value of it: {named}")
    own = (*depth, path[-1])
    if why and not decided and gone_to and list(depth) == list(path[:-1]) \
            and (row is None or first_open.key(row) == first_open.key(own) or in_icon(lit, row)):
        # the navigated row's own reading the bar starts with (icon_reading), the words past it none or a value of it
        head = icon_reading(lit, path[-1], gone_to[0], {*known, *gone_to[1]})
        rest = safety.plain(stop_kept(lit)[len(head):]) if head else ""
        own_values = {safety.plain(v) for v in (values or {}).get(first_open.key(own)[-1], ())}
        if head and (not rest or rest in own_values):
            row, why = own, ""
        elif icon_behind(lit, path[-1], gone_to[0], {*known, *gone_to[1]}):
            # the label behind the icon read as a letter or two (camkit.match.ICON) is the navigated row, which the page
            # model saw drawn with an icon, the words past it none or a value of it: the live OCR spelled the icon
            # otherwise than the page model's (kit2_chk_drive_1119: "R" for "i"), even as a short row of another page
            rest = safety.plain(stop_kept(behind(lit))[len(stop_kept(path[-1])):])
            if not rest or rest in own_values:
                row, why = own, ""
    bar = next((k for k in known if isinstance(k, SubmenuBar)), None)
    if not decided and bar is not None and len(path) > 1 and list(depth) == list(path[:-1]) \
            and (why or first_open.key(row) != first_open.key(own)) \
            and (row is None or first_open.key(row) == first_open.key(own)
                 or first_open.key(row)[-1] in {safety.plain(r) for r in bar.readings}) \
            and submenu_tied(lit, path[-1], bar):
        # a submenu has no page model: the --path's own row on its own page, its bar tied to it by the page as read
        # live on the bar's own frame (submenu_tied: kit2_fin_look_varsh's "fVar. Shutter Set.", kit2_fin_look_brtype1's
        # "Bracket Type Cont. Bracket", 2026-11-19)
        row, why = own, ""
    if why:
        return why, None
    if list(depth) == list(path[:-1]) and first_open.key(row) == first_open.key((*depth, path[-1])):
        return "", tuple(path)
    if not seen.seen(row):
        return f"the lit row reads {lit.strip()!r}, a row this camera has not been seen to open: {named}", None
    return "", row


def behind(lit) -> str:
    """The lit bar's text without the icon read in front of it as a stray mark or a letter or two, by the kit's one rule
    for such an icon (camkit.match.ICON): "R Peaking Color White" -> "Peaking Color White"; the text as it is where
    nothing is so read."""
    return match.ICON.sub("", str(lit or "").strip()).strip()


def in_icon(lit, row) -> bool:
    """Whether the row lit_refused's longest-label rule read the bar as (`row`, a path) is no more than the icon read in
    front of the label (behind's): "R Peaking Color White" read as the row "R", a row the kit knows on another page
    (Picture Profile's Color Depth R; kit2_chk_drive_1119, 2026-11-19)."""
    text, cut = str(lit or "").strip(), behind(lit)
    if row is None or not cut or cut == text:
        return False
    icon, label = safety.plain(text[:len(text) - len(cut)]), first_open.key(row)[-1]
    return bool(label) and len(label) <= len(icon) and icon.startswith(label)


def icon_behind(lit: str, label: str, row, others=()) -> bool:
    """Whether the lit bar's text `lit` is the page model row `row` (the one go_to reached for the --path's row `label`)
    with its icon read in front as a stray mark or a letter or two, by camkit.match.ICON's rule (behind), whatever the
    letter: the row's label is `label` (compared plain); the page model saw the row drawn with an icon (a reading of it
    is the label behind such an icon: "i Peaking Color"); the text behind the icon starts with the label, both with
    their last stop kept (stop_kept), alone or before what is no letter or digit of a longer word; and no name the kit
    knows another row by (`others`, as icon_reading takes them) is what the text as read, or behind the icon, starts
    with, unless it lies within the icon itself ("R", Color Depth's row, read for the icon of Peaking Color). So "AF
    Assist On" is never the row "Assist" where another row is read "AF Assist", and a row the page model never saw with
    an icon takes no letter in front."""
    want = safety.plain(label or "")
    if not want or not isinstance(row, dict) or safety.plain(row.get("label") or "") != want:
        return False
    if not any(behind(r) != r.strip() and safety.plain(behind(r)) == want for r in row_readings(row)):
        return False                        # the page model never saw an icon in front of this row's label
    text, cut = str(lit or "").strip(), behind(lit)
    head, seen = stop_kept(label), stop_kept(cut)
    if cut == text or not seen.startswith(head) or seen[len(head):len(head) + 1].isalnum():
        return False
    full, icon = safety.plain(text), safety.plain(text[:len(text) - len(cut)])
    for other in others:
        p = safety.plain(other) if isinstance(other, str) else ""
        if not p or p == want:
            continue
        if (full.startswith(p) and not full[len(p):len(p) + 1].isalnum() and len(p) > len(icon)) or \
                (len(p) > len(want) and seen.startswith(p) and not seen[len(p):len(p) + 1].isalnum()):
            return False
    return True


# what stands before a row's label in a reading of it, compared plain: nothing (the label itself), or the row's icon
# read as a letter or two ("S Exposure Comp.", "QEnlarge Image"), at most two letters or digits, then at most one space
# (icon_reading)
ICON_LEAD = re.compile(r"[0-9a-z]{0,2} ?")


def stop_kept(text) -> str:
    """`text` as safety.plain compares it, but its last stop kept ("S Exposure Comp." -> "s exposure comp."): plain
    leaves out the signs at a text's end, so a reading ending in a stop would else be followed, in the lit bar, by that
    stop and anything glued on after it ("S Exposure Comp.ensation")."""
    return safety.plain(f"{str(text or '').strip()}0")[:-1]


def icon_reading(lit: str, label: str, row, others=()) -> str:
    """The reading of the page model row `row` (the one go_to reached for the --path's row `label`) that ties the lit
    bar's text `lit` to that row, as stop_kept gives it, or "": the row's label is `label` (compared plain); the reading,
    compared plain, is that label, or ends with it after at most two letters or digits and at most one space (ICON_LEAD:
    the row's icon read as a letter or two, "S Exposure Comp.", "QEnlarge Image"); the lit text starts with the reading, both with their
    last stop kept (stop_kept), alone or before what is no letter or digit of a longer word (Seen.lit_row's rule for a
    value after a label); and no reading the text so starts with is, compared plain, a name the kit knows another row by
    (`others`: the definition's row labels, the page model's and the page's own, and the page model's readings of other
    rows, other_names), so "AF Assist" is never the row "Assist"."""
    want, seen = safety.plain(label or ""), stop_kept(lit)
    if not want or not isinstance(row, dict) or safety.plain(row.get("label") or "") != want:
        return ""
    hits = {}
    for reading in row_readings(row):
        r, head = safety.plain(reading), stop_kept(reading)
        if r.endswith(want) and ICON_LEAD.fullmatch(r[:len(r) - len(want)]) and seen.startswith(head) \
                and not seen[len(head):len(head) + 1].isalnum():
            hits[head] = r
    if not hits or set(hits.values()) & ({safety.plain(x) for x in others if isinstance(x, str)} - {want}):
        return ""
    return max(hits, key=len)


class SubmenuBar(NamedTuple):
    """The lit bar of the submenu page shown, read with the page's labels on one frame (submenu_bar, which shown_labels
    adds to the labels it gives lit_refused; no str, so every check of `known` that reads labels passes it by)."""
    lit: str            # the bar's whole text, as highlighted reads it on that frame
    label: str          # its text in the label column (centres up to LABEL_END), as OCR reads it
    values: tuple       # ((text, x0, x1), ...): its texts in the value column, left to right
    label_end: int      # x where the label column's text ends
    bar_end: int        # x where the orange bar ends
    readings: tuple     # the lit row's readings among the page's labels read live (camkit.live.submenu_labels)
    others: tuple       # every reading of the page's other rows


LABEL_END = 470         # x: a submenu row's label column ends here (camkit.live.submenu_texts), its value column begins
VALUE_GAP = 40          # px at least between a bar's label and its value: a value stands apart (a word space is ~10)
VALUE_RIGHT = 12        # px at most between a bar's value and the bar's right end: a value is right-aligned (3-4 seen)
# a letter or digit, glued on or set apart by a space, read for a row's icon before its label ("fVar. Shutter Set.")
ICON_ONE = re.compile(r"[0-9a-z] ?")


def submenu_tied(lit: str, label: str, bar) -> bool:
    """Whether the lit bar read as `lit` is, beyond doubt, the submenu row `label` (the --path's last), by `bar` (a
    SubmenuBar read on the bar's own frame), compared as stop_kept compares (plain, the last stop kept), all of: `bar`
    was read on this very bar (its text is `lit`); the bar's label column reads `label`, alone or after one letter or
    digit read for the row's icon (ICON_ONE); every reading of the lit row among the page's labels read live is
    `label` so, and one is `label` itself (the reader's, which leaves the icon out); no other row of the page reads as
    `label` or a longer label that starts with it, with or without such a letter; and whatever the bar reads past its
    label column stands in the value column, VALUE_GAP or more past the label's end and ending within VALUE_RIGHT of the
    bar's right end, the bar's text being exactly the two. So "Bracket Type Cont. Bracket" (the value right-aligned at
    x 495-637) is Bracket Type and "fVar. Shutter Set." Var. Shutter Set.; a bar whose label column reads longer than
    `label`, a page with another row named so or longer, a lit row the reader reads otherwise, words past the label
    within the label column or not at the bar's end, two letters before it, or no reading at all, are not."""
    if not isinstance(bar, SubmenuBar) or not bar.lit.strip() or " ".join(str(lit or "").split()) != " ".join(bar.lit.split()):
        return False
    head = stop_kept(label)
    if not head:
        return False

    def names(text) -> bool:
        t = stop_kept(text)
        return t == head or (t.endswith(head) and ICON_ONE.fullmatch(t[:len(t) - len(head)]) is not None)

    if not names(bar.label) or not bar.readings or not all(names(r) for r in bar.readings) \
            or not any(stop_kept(r) == head for r in bar.readings):
        return False
    for other in bar.others:
        t = stop_kept(other)
        for cut in (t, t[1:].lstrip()):                 # with a letter read for an icon left out too
            if cut.startswith(head) and not cut[len(head):len(head) + 1].isalnum():
                return False
    if bar.values and (any(x0 < bar.label_end + VALUE_GAP for _, x0, _ in bar.values)
                       or max(x1 for *_, x1 in bar.values) < bar.bar_end - VALUE_RIGHT):
        return False
    return safety.plain(lit) == safety.plain(" ".join([bar.label, *(t for t, *_ in bar.values)]))


def bar_reading(lines, box, lit: str, rows, i: int) -> SubmenuBar:
    """The SubmenuBar of the lit row `i` of a submenu page: `lines`, OCR's lines inside its orange bar `box` (x0, y0, x1,
    y1); `lit`, the bar's text as highlighted reads it; `rows`, the page's labels read live (submenu_labels' rows)."""
    def readings(r) -> tuple:
        return tuple(t for t in (r.get("label"), *(r.get("readings") or ())) if isinstance(t, str) and t.strip())
    left = [ln for ln in lines if ln.x + ln.w / 2 <= LABEL_END]
    right = sorted((ln for ln in lines if ln.x + ln.w / 2 > LABEL_END), key=lambda ln: ln.x)
    return SubmenuBar(str(lit or ""), " ".join(ln.text for ln in left).strip(),
                      tuple((ln.text, ln.x, ln.x + ln.w) for ln in right), max((ln.x + ln.w for ln in left), default=0),
                      int(box[2]), readings(rows[i]),
                      tuple(t for j, r in enumerate(rows) if j != i for t in readings(r)))


def submenu_bar(cam, rows) -> SubmenuBar | None:
    """The SubmenuBar of the submenu page on screen (rows: its labels as submenu_labels read them on this frame), or None
    where it cannot be read: a screen not read as a submenu, no lit row among its rows, no orange bar found, a bar
    outside that row, a frame OCR cannot read."""
    try:
        f, s = cam.frame, cam.read()
        i = s.row
        if s.kind != "submenu" or not isinstance(i, int) or not 0 <= i < min(len(rows), len(s.rows)):
            return None
        box, whole = lit_found(f.image)
        top, bottom = s.rows[i]
        if not box or not whole or not top <= (box[1] + box[3]) / 2 <= bottom:
            return None
        lines = [ln for ln in ocr.read([f.path])[f.path] if ln.inside(box)]
        return bar_reading(lines, box, highlighted(f.image, f.path), rows, i)
    except Exception:       # noqa: BLE001 (no reading: lit_refused's rule stands alone)
        return None


def scan_row(cycle, model, j) -> dict | None:
    """The page model's row at the page scan's position `j` (where crawl_run.go_to went), or None where it has none."""
    if isinstance(j, bool) or not isinstance(j, int) or j < 0:
        return None
    try:
        row = model[cycle[j]["page"]]["rows"][cycle[j]["row"]]
    except (IndexError, KeyError, TypeError):
        return None
    return row if isinstance(row, dict) else None


def other_names(model, label: str) -> set:
    """Every label and reading the page model (model: {page key: page}) keeps of a row whose label is not `label`
    (compared plain; a namesake on another page, My Menu's, is the row's own): names a reading of the row `label` must
    not be to tie a lit bar to it (icon_reading)."""
    want = safety.plain(label or "")
    return {t for page in (model or {}).values() if isinstance(page, dict)
            for row in page.get("rows") or [] if isinstance(row, dict) and safety.plain(row.get("label") or "") != want
            for t in row_readings(row)}


def shown_labels(cam, cycle, model) -> list:
    """The row labels of the menu page shown, read as the crawl reads them: a submenu page's live, its every reading
    (camkit.live.submenu_labels: OCR and the reader), and its lit bar read with them on that frame (submenu_bar: a
    SubmenuBar, where it can be read), a top-level page's from the page scan's model (page_labels); [] where they
    cannot be read."""
    try:
        if cam.read().kind == "submenu":
            rows = submenu_labels(cam)[1]
            bar = submenu_bar(cam, rows)
            return [t for r in rows for t in (r.get("label"), *(r.get("readings") or ())) if t] + ([bar] if bar else [])
        return page_labels(cam.read(), cycle, model)
    except Exception:       # noqa: BLE001 (labels not read: the rule falls back on what the kit knows)
        return []


def next_depth(depth, key: str, before: str, opened, now: str):
    """The labels above the menu page shown after a press of `key` on a screen of kind `before`: the row `opened` (its
    path) when the press opened a submenu; unknown (None) after a MENU or a Left on a menu page, which may leave it;
    else as they were."""
    if opened and now == "submenu":
        return list(opened)
    if canonical_key(key) in ("menu", "left") and before in ROW_PAGES_OPENED:
        return None
    return depth


def first_open_or_exit(a, seen=None) -> str | None:
    """The --path's last label when the run opens it (a --press of OPENERS) and this camera has not been seen to open it
    (camkit.first_open), else None: its first open goes under the link-loss procedure as an armed press does
    (RESTORE_BY_HAND first, one read after it), and the run's start and end downloads are its check. Stops before
    anything connects where a label above it, which the walk opens, is not seen either (each is opened the first time
    in a run of its own), where --press is not Right alone (a first open is a look), or where the camera's reviewed
    scope holds no current blank-cards statement (camkit.statements). Not on an --owner run: the owner route writes its
    own RESTORE_BY_HAND and asks the owner's typed word."""
    if getattr(a, "owner", False):
        return None
    keys = [parse_press(p) for p in a.press]
    opens = any(k in OPENERS for k, _, _ in keys)
    seen = seen if seen is not None else first_open.seen_record()
    fresh = [p for p in seen.unseen(a.path) if len(p) < len(a.path) or opens]
    if not fresh:
        return None
    label = " > ".join(fresh[0])
    if len(fresh[0]) < len(a.path):
        sys.exit(f"{label!r} has not been seen opened on this body: open it first in a run of its own (its --path, "
                 "--press right), then the rows below it: nothing was sent to the camera")
    if [(k, y) for k, y, _ in keys] != [("right", None)]:
        sys.exit(f"{label!r} has not been seen opened on this body, and its first open is a look: --press right alone, "
                 "the presses you meant in the next run: nothing was sent to the camera")
    why = cards_statement_refused("drive.py")
    if why:
        sys.exit(f"{label!r} has not been seen opened on this body, and {why}: nothing was sent to the camera")
    print(f"{label!r} has not been seen opened on this body: it opens under the link-loss procedure (RESTORE_BY_HAND "
          "first; taken away once the start file is checked to be unchanged)", flush=True)
    return a.path[-1]


def intend_by_hand(run, before: Path, label: str, entry: str, why: str = "") -> Path:
    """RESTORE_BY_HAND written before the run's armed press that may drop the link is handed over (camkit.runs: in the
    run root and the clone's own runs/ for the camera), naming the start file `before`: the intent, so that a crash, a
    lost link or a question left open after that press leaves no camera a later run would start from. When it cannot
    be written, nothing is pressed: what was written is taken away and a RuntimeError says so. `why`: the marker's words,
    for a row's first open on the body."""
    try:
        return mark_restore_by_hand(run.root, run.dir.name, before,
                                    why or f"the last press inside {label!r} ({entry}) may drop the link")
    except Exception as e:
        with contextlib.suppress(Exception):
            clear_restore_by_hand(run.root)
        raise RuntimeError(f"RESTORE_BY_HAND could not be written ({type(e).__name__}: {e}): nothing was pressed") from e


def after_armed(cam, grip: str | None, kinds=safety.SHOWN_KINDS) -> tuple:
    """(the screen's kind, its text, why it cannot be judged or "") read once right after the run's armed press that may
    drop the link (camkit.live.LiveCamera.refresh, guarded): a read that fails, a frame that is black (camkit.live.black)
    or of no kind of `kinds`, or a text that cannot be read, is not judged, and then the restore-by-hand marker stays and
    nothing more is pressed (docs/decisions/0005). `kinds`: safety.SHOWN_KINDS for the owner route's armed presses (an
    unknown screen, a slider among the kinds it does not read); safety.FIRST_OPEN_KINDS for a row's first open alone,
    which also reads the option screens MENU leaves (a slider, number fields, a table...), never an unknown screen."""
    try:
        kind = getattr(cam.refresh("after-armed"), "kind", None)
        text, dark = screen_text(cam, grip), black(cam.frame)
    except Exception as e:
        return None, "", f"the screen after it could not be read ({type(e).__name__}: {e})"
    if dark:
        return kind, text, "the frame after it is black"
    if kind not in kinds:
        return kind, text, f"the screen after it reads as {kind!r}, no kind the kit reads"
    if not (text or "").strip():
        return kind, text, "no text could be read on the screen after it"
    return kind, text, ""


def cancel_question(cam, grip: str | None, row: str, tries: int = 3) -> bool:
    """The owner row `row`'s own question (safety.own_question) cancelled with MENU, never Enter: at most `tries` MENUs,
    each a cleanup press that a STOP never holds (camkit.live.LiveCamera.cancel_to_menu, one MENU each), until the screen
    read after one is a screen the kit reads (after_armed's checks) that is no longer that question. False when MENU
    did not clear it, or the link stopped answering: then a person cancels it on the camera."""
    for _ in range(tries):
        try:
            cam.cancel_to_menu(1)
            kind, text, why = cam.read().kind, screen_text(cam, grip), ""
            if black(cam.frame) or kind not in safety.SHOWN_KINDS or not (text or "").strip():
                why = "unread"
        except Exception:
            return False
        if not why and not safety.own_question(kind, text, row):
            return True
    return False


def owner_path(paths: list, rows: dict) -> tuple:
    """(the entry of the owner row the --path ends on, its info, why the path is refused or ""), for --owner's rows
    ({entry: info}): the --path is the row's place from its first row on, "Tab > Group" left off (the path the decision
    writes, or the one place the kit knows a label alone in); exactly one entry may match; no
    other label of the path may be an owner row (one row per run, opened by this run's own presses, never by the walk to
    it)."""
    def same(a, b) -> bool:
        return [safety.plain(x) for x in a] == [safety.plain(x) for x in b]
    found = [e for e, i in rows.items() if (same(i["path"][2:], paths) if i.get("path") else False)]
    if len(found) != 1:
        return None, None, ("--owner: the last label of --path is no row an owner decision names (a row named by its path "
                            "takes --path from its first row on)" if not found else
                            f"--owner: --path matches {len(found)} rows of the owner decisions ({', '.join(found)})")
    early = [x for x in paths[:-1] if any(safety.plain(x) == safety.plain(i["label"]) for i in rows.values())]
    if early:
        return None, None, (f"--path {early[0]!r}: an owner decision's row is opened only as the last label of --path, "
                            "one per run (docs/decisions/0008)")
    return found[0], rows[found[0]], ""


def inside_refused(key: str, cam, inside: dict, options) -> str:
    """Why drive.py may not send `key` while a row a network decision opened is open (inside: {"row", "address",
    "identity"}), or "", whatever the screen reads as: on an address screen, or once a screen named identity or
    credentials, any key but MENU; else what safety.look_refused refuses (anything but up, down, MENU and Enter on an
    option the decision names for the row, `options`, the lit bar read now)."""
    name = press_name(key)
    if inside["address"] or inside["identity"]:
        return "" if name in safety.SHOOTING_FREE else (
            f"{'an address screen' if inside['address'] else 'a screen naming identity or credentials, or of no known kind,'}"
            f" is open inside {inside['row']!r}: no key but MENU goes out on it (docs/decisions/0008)")
    lit = highlighted(cam.frame.image, cam.frame.path) if key in ENTERS else ""      # a dial or C4 is refused there too
    return safety.look_refused(key, lit, inside["row"], (options or {}).get(inside["row"]) if not inside.get("look")
                               else None)


# Inside a row a network decision opened, the presses after which it may be left: MENU, and an Enter inside_refused
# let through (an option the decision names)
CLOSES = ("menu", *ENTERS)


def network_left(now, opened_from, closing: bool, lit: str = "", row: str = "", suspect=None, own=None,
                 readings=None, labels=None) -> bool:
    """Whether the row a network decision opened has been left, the screen read right after the press being `now`:
    only when that press was a MENU, or an Enter on an option the decision names (`closing`: CLOSES; main() spends it
    on this one read, so a MENU the camera ignored never ends the row on a later press), AND `now` is the shooting
    screen, or the page the row was opened from (`opened_from`, the screen read before the press that opened it:
    same_position) with its lit bar (`lit`, as read now) reading the row `row` itself, as its label or as a reading of
    it with its page's icon glued on (`readings`, runner.network_readings: safety.bar_on_row), or with that icon as the
    live bar shows it where the run's known labels are given (`labels`, runner.label_readings: icon_slip): a popup over
    the dimmed page lights an option, never the row, and a bar that cannot be read keeps the row open. Never on a
    screen's kind alone, never on the press that opened the row: a camera slow to draw the row's list still shows the
    page after it, and a list misread as a menu page reads as one. MENU that lands on another page, or on the Main
    tiles, leaves the row open: another MENU closes the menu onto the shooting screen. Where the row's own screen read
    as the shooting screen before any closing key (`suspect`, that screen: main() marks it), a frame read as the
    shooting screen ends the row only when it is not that screen (same_state) and the camera's own picture of the screen
    reads as the shooting screen too (`own()`, its kind: live.osd_kind); a picture that cannot be had keeps the row open
    (camkit.live.menu_closed)."""
    if not closing:
        return False
    if getattr(now, "kind", None) == "shooting":
        if suspect is None:
            return True
        try:
            if same_state(now, suspect):
                return False
            return own is not None and own() == "shooting"
        except Exception:                   # a screen or a picture that cannot be had is no way out
            return False
    try:
        if not same_position(now, opened_from):
            return False
    except Exception:                       # a screen that cannot be compared is no way out
        return False
    return safety.bar_on_row(lit, row or "", readings, labels)


def network_path(paths: list, network) -> tuple:
    """(the --path labels a dated owner decision opens, the address screen the path ends on or None, why the path is
    refused or "") for --network's rows `network` ({row: date}; empty without --network). A label a decision names
    (safety.network_lifted, an address screen included) needs no --allow; any other label is judged as before
    (main). An address screen is looked at only as the last label of --path, and only one: enter_any would press Right
    on any label before the last, taking it for a submenu."""
    lifted = [x for x in paths if network and safety.network_lifted(x, network, screens=True)]
    addresses = [x for x in paths if safety.address_screen(x)]
    if addresses and (len(addresses) > 1 or addresses[-1] != paths[-1]):
        return lifted, None, (f"--path {addresses[0]!r}: an address screen is opened only as the last label of --path, "
                              "one per run, and looked at with one press (docs/decisions/0008)")
    return lifted, (addresses[-1] if addresses and addresses[-1] in lifted else None), ""


def look_path_or_exit(paths: list, seen, address=None) -> tuple:
    """(the --path labels a look lap opens that never_open names, the address screen the path ends on or None) for a run
    given --network (docs/decisions/0024). A label safety.look_lap_refused refuses, never-open or not, stops the run
    before anything connects: what OWNER_NEVER names, and a format, delete or reset this body's records have not shown
    opened (`seen`: camkit.first_open.Seen, the path up to the label judged; None, an --owner run's, sees nothing), whose
    first open is the owner's own run. An address screen a look lap opens is looked at as one a decision names
    (`address`, network_path's), as the last label alone."""
    looked = []
    for i, label in enumerate(paths):
        was = bool(seen is not None and seen.seen(paths[:i + 1]))
        why = safety.look_lap_refused(label, was)
        if why:
            sys.exit(f"{label!r}: {why}: nothing was sent to the camera")
        if safety.never_open(label):
            looked.append(label)
    if address is None and paths and paths[-1] in looked and safety.address_screen(paths[-1]):
        address = paths[-1]
    return looked, address


def camera_network(network, address) -> dict:
    """The rows the camera's own checks may open for a --network run (LiveCamera, press_refused): the Wi-Fi and
    Bluetooth settings the decision names, and the address screen the path ends on (address) when one does, never
    another address screen the decision names."""
    out = {r: d for r, d in network.items() if not safety.address_screen(r)}
    if address:
        out.update({r: d for r, d in network.items()
                    if safety.address_screen(r) and safety.network_lifted(address, {r: d}, screens=True)})
    return out


def screen_lines(cam, grip: str | None) -> list:
    """The texts of the OCR lines on the screen (and, held vertically, on the frame turned upright that screen_text
    saved): what safety.address_fields reads an address screen from."""
    f = cam.frame
    if getattr(cam, "blank", False):
        return []                   # a blanked row's frame (an owner row whose values are withheld): never read
    out = [ln.text for ln in ocr.read([f.path])[f.path]]
    up = f.path.with_name(f"{f.path.stem}_upright.png")
    if grip and up.exists():
        out += [ln.text for ln in ocr.read([up])[up]]
    return out


def shown_screen(cam, grip: str | None, text: str, hide: bool, labels=(), values=(), logged: bool = False,
                 kind: str | None = None, options=(), by_row=None, page=()) -> tuple:
    """(what the console shows of a screen, what drive.jsonl keeps of it): its text, or, hidden, what
    safety.kept_screen keeps of it (by its kind: the shooting screen as its kind alone; else its whole row labels and
    field names, a list's known option names, a notice as safety.notice_kept keeps it) and the count of lines withheld,
    never a value (labels: the menu's row labels as the page model and the definition know them, runner.known_labels;
    values: the values they know for the rows, runner.known_values, never kept; options: the definition's value names
    for the row whose list this is, runner.defined_values; by_row: runner.row_values, for a notice; page: the page
    model's row labels of the scan page shown, page_labels, without which no line of a letter or two is kept). logged
    (an owner decision's "values": "logged", inside its row): the console as hidden, saying "(values in drive.jsonl)", and
    drive.jsonl keeps the text besides: the run's files hold the values, never the console (which a hosted agent may
    read). A blanked row's screen (cam.blank) is kept as "blanked" alone: its frame is black and was never read."""
    if getattr(cam, "blank", False):
        return safety.kept_said({"blanked": True}), {"blanked": True}
    if not hide:
        return repr((text or "")[:150]), {"text": text}
    if kind is None:
        with contextlib.suppress(Exception):
            kind = cam.read().kind
    kept = safety.kept_screen(kind, screen_lines(cam, grip), labels, values, options, by_row, page)
    if logged:
        return f"{safety.kept_said(kept)} (values in drive.jsonl)", {**kept, "text": text}
    return safety.kept_said(kept), kept


def page_labels(now, cycle, model) -> list:
    """The page model's row labels of the scan page the screen read as `now` is (camkit.screen.same_position against the
    scan's cycle), or [] when it is none (a row's own list, a notice, a screen the scan does not know): the only labels a
    withheld screen keeps a line of a letter or two for (safety.screen_fields' page)."""
    try:
        j = next((i for i, p in enumerate(cycle or ()) if same_position(now, p["screen"])), None)
    except Exception:                       # a screen that cannot be compared is no page
        return []
    page = (model or {}).get(cycle[j].get("page")) if j is not None else None
    return [r["label"] for r in (page or {}).get("rows") or [] if isinstance(r, dict) and isinstance(r.get("label"), str)]


def network_shown(kind: str, text: str, inside, address: bool, network: bool) -> bool:
    """Whether a screen is shown and kept as safety.kept_screen keeps it (shown_screen's hide), never its text: every
    screen of an address run, a --network run or an --owner run, from the run's start to its end, whatever its kind, its
    text or the row open (2026-11-14: a look at the Wi-Fi and Bluetooth rows printed a greyed row's notice with its
    blocker's state, a list's current value and, after MENU, the shooting screen's status line). A run without
    --network or --owner shows every screen as ever."""
    return bool(address or network)


withheld = safety.quoted_withheld        # a refusal's or an error's quoted texts withheld (address runs, network rows)


def owner_kept(cam, grip, text: str, labels, values, info: dict, kind: str | None = None, options=(),
               by_row=None) -> tuple:
    """(console, record) of a screen met in the owner row of `info`, its opening's after-armed screen among them: as
    every screen inside it is kept (shown_screen hidden), its text in drive.jsonl only where the decision logs values."""
    return shown_screen(cam, grip, text, True, labels, values, bool(info.get("logged")), kind, options, by_row)


def menu_only(inside: dict, kind: str, text: str) -> str | None:
    """Why only MENU may go out from this screen on inside the row open (`inside`): safety.owner_menu_only inside the
    owner row (a keyboard, an entry screen, credentials or a connection, the serial number; whatever the decision says
    of values), safety.inside_menu_only inside a row a network decision opened."""
    if inside.get("owner"):
        return safety.owner_menu_only(inside.get("class"), kind, text, inside["row"], inside.get("blank", False))
    return safety.inside_menu_only(inside.get("class"), kind, text, inside["row"])


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
    """The screen's text; held vertically, the text of the frame turned upright follows it. A blanked row's frame (an
    owner row whose values are withheld, cam.blank) is never read, nor turned and saved upright: ""."""
    if getattr(cam, "blank", False):
        return ""
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


UNFINISHED = "the run did not finish: its restore stopped short, and the camera is not known to be on its start file"


def unfinished_line(a, ok: bool, before: Path, network=None, address=None, owner_entry=None, owner_info=None,
                    marker=None) -> dict:
    """drive.jsonl's result line for a run whose restore ended early (runner.restoring's EXIT_UNRESTORED, or an armed
    press's restore by hand): what the run was asked (its path, presses and note, the decision's rows), whether its
    presses went (`ok`), the start file, and that it did not finish and was not restored (UNFINISHED). No screen's text,
    no screen at all, and no record's value: the run's record, where the file was left empty (2026-11-14)."""
    return {"path": a.path, "presses": a.press, "note": a.note, "completed": ok,
            **({"network": dict(network)} if network else {}),
            **({"address_screen": address} if address else {}),
            **({"owner": {owner_entry: {k: v for k, v in owner_info.items() if k != "why"}}} if owner_info else {}),
            "before": before.name, "after": None, "restore": "not finished", "outcome": UNFINISHED,
            **({"marker": marker.name} if marker else {})}


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
    ap.add_argument("--confirm", nargs="?", const=True, default=None, metavar="SCREEN TEXT",
                    help="with --owner: the owner route's step or armed last press (the person at the terminal types the "
                         "row's name); without it: \"SCREEN TEXT\", the whole text of the one screen whose Enter this "
                         "run may send past the shape check, once, never past the confirmation words")
    add_info_ok_argument(ap)
    ap.add_argument("--wait", type=float, default=1.0, help="seconds after the last press")
    ap.add_argument("--run", default="kit2_drive")
    ap.add_argument("--note", default="", help="what this drive tests (kept with the result)")
    add_scan_argument(ap)
    ap.add_argument("--grip", choices=sorted(GRIPS), help="the camera is held vertically: read turned screens upright")
    add_network_argument(ap)
    add_owner_argument(ap)
    a = ap.parse_args()
    # --confirm: with --owner the owner route's flag (typed row name, armed last press); without it the one screen whose
    # Enter the run may send past the shape check, named by its whole text, once, never past the confirmation words
    confirm_phrase = None
    if a.owner and isinstance(a.confirm, str):
        sys.exit("--owner --confirm takes no screen text: the person at the terminal types the row's name instead")
    if a.confirm is not None and not a.owner:
        confirm_phrase = confirm_phrase_or_exit(a.confirm)
    a.confirm = bool(a.owner and a.confirm)
    # --info-ok "ROW=PHRASE": a plain notice met after the run's presses, its OK taken where it is that notice alone,
    # as the crawl and the provers take theirs (proving.screens.notice_refused); ROW one of --path's labels
    if a.info_ok and (a.owner or a.network):
        sys.exit("--info-ok passes no notice on a --network or --owner run: their rows are looked at, or armed, only")
    named_notes = info_ok_or_exit(a.info_ok, rows=a.path, labels=a.path) if a.info_ok else {}
    for label in a.allow:
        # nothing on the cards (2026-11-01, the owner: "Please don't delete the cards"), Initialize, Reset Network Set.,
        # credentials, nor the camera's identity, a connection or its region (decisions 4, 5, 8 and 9), nor a Wi-Fi or
        # Bluetooth setting or an address screen, which only a dated decision opens (--network)
        why = safety.allow_refused(label)
        if why:
            sys.exit(f"--allow {label!r}: {why}")
    # the dated owner decisions that open Wi-Fi and Bluetooth rows, read before anything connects (a decision naming
    # what none opens stops the run here); logged in the run once it is open
    network, options, _ = network_decided_or_exit(look=not a.owner) if a.network else ({}, {}, "")
    lifted, address, why = network_path(a.path, network)
    if why:
        sys.exit(why)
    # a look lap (docs/decisions/0024): every --network run but an --owner one, whose row is its decision's alone. A
    # --path label it opens needs no --allow; one it never opens (OWNER_NEVER's, and a format, delete or reset this body
    # has not been seen to open, its first open being the owner's own run) stops the run here
    look = bool(a.network and not a.owner)
    if look:
        print(LOOK_LAP, flush=True)
        looked, address = look_path_or_exit(a.path, first_open.seen_record(), address)
        lifted += looked
    # the one row an owner decision opens for this run (--owner): the last label of --path, told by the menu places the
    # page scan and the definition know; read before anything connects, as the network decisions are
    scan = load_scan(a.scan) if a.owner else None
    owner_entry, owner_info, owner_cam, owner_label, owner_place = None, None, None, None, []
    if a.owner:
        rows = owner_decided_or_exit(scan[1])
        owner_entry, owner_info, why = owner_path(a.path, rows)
        if why:
            sys.exit(why)
        owner_label = owner_info["label"]
        # the row's place, [tab, group, row, ...]: the path the decision writes, or the one place the kit knows a label
        # alone in; its tab and group are where the run goes and what the page shown must read (place_refused)
        owner_place = list(owner_info.get("path") or [])
        if len(owner_place) < 3:
            sys.exit(f"--owner: the decision gives {owner_entry!r} no tab and group: nothing was sent to the camera")
        owner_cam = {owner_label: owner_info}           # all the camera is given: one row
        # a row whose opening may drop the link the run is on (IP Address Setting dropped it, 2026-11-14) opens only as
        # the armed last press: a run without --confirm, or a decision not naming it under "confirm", could only walk
        # there and be refused, so it stops before anything connects
        if owner_info.get("acts_on_open") and safety.link_risk_open(owner_label) and not (
                a.confirm and owner_info.get("confirm")):
            sys.exit(f"--owner: opening {owner_entry!r} may drop the link the run is on, so it opens only as the armed "
                     "last press of a run given --confirm, the row under \"confirm\" with \"link_loss\": true "
                     "(docs/decisions/0008): nothing was sent to the camera")
        # a credentials row's options are its own listed values (the page model's, the definition's), never a key
        why = safety.owner_values_refused(owner_info, network_values(owner_cam, scan[1]).get(owner_label, ()))
        if why:
            sys.exit(f"--owner: {why}: nothing was sent to the camera")
    for i, label in enumerate(a.path):
        if label in lifted:
            continue                # a dated owner decision names it, or a look lap opens it (--network): no --allow
        if owner_info and i == len(a.path) - 1:
            continue                # the row an owner decision names (--owner): owner_path saw that it is that row
        hard = safety.allow_refused(label)
        if hard:
            sys.exit(f"{label!r}: {hard}")
        why = safety.never_open(label)
        if why and label not in a.allow:
            sys.exit(f"{label!r} is never-open ({why}); name it with --allow to enter it")
    why = press_args_refused(a.press) or on_shooting_refused(a.on_shooting) or c4_presses_refused(a.press, a.c4_press)
    if why:
        sys.exit(why)
    # the --path's last row when this camera has not been seen to open it: a look under the link-loss procedure
    seen = None if a.owner else first_open.seen_record()       # the rows this camera has been seen to open
    first_label = first_open_or_exit(a, seen)
    ledger = coverage.drive_gate(a)     # what the coverage ledger says of the --path, printed; drive.py never skips
    on_shooting = frozenset(safety.canonical_input(k) for k in a.on_shooting)
    cam_network = camera_network(network, address)
    # a row a network decision opened, while it is open: {"row", "class", "address", "identity", "from": the screen it
    # was opened from, "closing": whether a MENU or an Enter on a named option has gone out since, "suspect": the row's
    # own screen when it read as the shooting screen before any closing key}
    inside = None

    def say(message: str) -> str:
        """A refusal or an error as printed: its quoted texts withheld on a --network or --owner run (a row's bar can
        carry an identity value) and on an address run."""
        return withheld(message) if address or a.network or a.owner else message

    def kind_now() -> str:
        """The screen's kind as the network checks judge it: inside a row whose own screen read as the shooting screen
        before any closing key went out ("suspect"), a frame read as the shooting screen is of no known kind (MENU
        alone, its field names only: safety.inside_menu_only); the link still judges it as the shooting screen."""
        kind = cam.read().kind
        return "unknown" if kind == "shooting" and inside and inside.get("suspect") is not None else kind

    def shown(t: str) -> tuple:
        """(console, record) of a screen whose text is t (network_shown): on a --network or --owner run, every screen
        from the run's start to its end as safety.kept_screen keeps it, never a line that is a value the kit knows nor
        which option is current; inside the owner row, its text kept in drive.jsonl alone where the decision logs
        values."""
        kind = kind_now()
        hide = network_shown(kind, t, inside, bool(address), a.network or a.owner)
        logged = bool(inside and inside.get("owner") and inside.get("logged"))
        names = defined.get(inside["row"], ()) if inside else ()       # the definition's option names for the row
        # a line of a letter or two is kept only as a row label of the scan page shown, never inside a row
        here = page_labels(cam.read(), cycle, model) if hide and not inside else []
        return shown_screen(cam, a.grip, t, hide, labels, told, logged, kind, names, by_row, here)
    cycle, model = scan if scan is not None else load_scan(a.scan)
    # the row labels the kit knows, against which a lit bar a press is about to open is read (lit_refused)
    known_rows = (known_labels(model) | row_labels(definition())) if seen is not None else set()
    row_vals = ({safety.plain(k): v for k, v in row_values(model).items()} if seen is not None else {})
    # the values the kit knows by row, which an opening check takes off a bar to judge the row alone (safety.row_judged:
    # every run but an --owner one, whose row is its decision's), a decided row's own as network_values gives them
    decided_values = network_values(cam_network, model) if a.network else {}
    values = decided_values if a.owner else {**row_values(model), **decided_values}
    if owner_info:
        values = {**values, **network_values(owner_cam, model)}
    readings = network_readings(cam_network, model) if a.network else {}
    # every label the kit knows a row by: a tail after a decided row's label whose values none knows makes none of them,
    # and a bar read whole as one is judged whole (safety.row_judged)
    known = label_readings(model) if a.network or not a.owner else None
    # what a withholding run keeps of a screen: the row labels the kit knows (the decisions' own rows among them), never
    # a value it knows; a list's option names as the definition gives them for its row; a notice judged by row_values
    labels = (known_labels(model) | set(network) | ({owner_label} if owner_label else set())
              if a.network or a.owner else set())
    told = known_values(model) if a.network or a.owner else set()
    defined = defined_values() if a.network or a.owner else {}
    by_row = row_values(model) if a.network or a.owner else {}
    run = Run(a.run)
    # the session's end says the records that differ by their keys alone and drive.jsonl keeps no value of them, unless
    # the owner row's decision logs values (runner.values_withheld, changes_kept)
    private = bool(address or a.network or a.owner)
    keep_values = not private or bool(owner_info and owner_info.get("logged"))
    confirm_left = 1 if confirm_phrase else 0           # --confirm "SCREEN TEXT": one Enter on that screen, then none
    if private:
        # its frames, drive.jsonl, events and downloads may hold addresses, credentials or logged values: the folder
        # owner-only from here, every file the run writes 0600 (camkit.runs; checked again at the end: seal)
        run.make_private()
    if a.network:
        log_network_decided(run, network, options)
    if owner_info:
        log_owner_decided(run, {owner_entry: owner_info})       # local readers only, and no batch reader ever
    if address:
        print(f"address screen {address!r}: each screen is shown and kept as its field names alone, no reader is asked "
              "once it is open, and no key but MENU goes out (docs/decisions/0008)", flush=True)
        run.log("address_run", row=address)
    if owner_info:
        print(f"owner row {owner_entry!r} ({owner_info['class']}): {safety.owner_said(owner_info)}"
              + ("; --confirm given" if a.confirm else "; no --confirm: nothing is confirmed or stepped") +
              " (docs/decisions/0008)", flush=True)
    if owner_info and a.confirm and safety.asks_person(owner_info):
        # the decision is a local file and --confirm a flag, both of which an agent can write: every confirming run in an
        # owner row waits for the person at the terminal, before anything connects (a never-choose option is an armed
        # press too)
        why = typed_word(owner_label, owner_place, armed_words(owner_info), run.root.name)
        run.log("owner_question", row=owner_label, answered=not why)
        if why:
            sys.exit(f"--owner: {why}")
    elif owner_info and a.confirm and owner_info.get("unattended"):
        print(f"the owner waived the terminal question for {owner_entry!r} in the decision (\"unattended\": true)",
              flush=True)
        run.log("owner_question", row=owner_label, waived=True)
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
    # the run's armed last press that may drop the link (safety.loses_link), once RESTORE_BY_HAND was written for it:
    # "pending" while it goes; "lost" when it may have gone and nothing after it can be judged, or its question stayed
    # open (stuck): no cleanup press, no remote restore; "question" when it brought up the row's own question, cancelled
    # with MENU; "answered" when the link answered with another screen. None: no such press, or it was refused before it
    # went (the marker taken away again)
    byhand, marker, question, stuck, unfinished, why_by_hand = None, None, None, False, False, ""
    # the press that went was the --path's first open on this body (first_open_or_exit), not an owner's armed press:
    # the marker then stays where any record differs at the end, and what the owner does is said in its own words
    first_went = False
    unreached = None        # the --path label the scan did not reach (NotReached): the run exits EXIT_INCOMPLETE
    try:
        with Link(run) as link:
            why = first_open.other_body(link, run.root.name)
            if why:
                sys.exit(f"{why}: nothing was sent to the camera")
            hdmi.attach(link)
            if screen.read(hdmi.grab(save=False)).kind in ("menu", "tiles"):
                link.press("menu", cleanup=True)
                time.sleep(1.0)
            wait_for(hdmi, ("shooting",), "the settings download", link=link)
            before = link.download("before")
            time.sleep(5)
            cam = LiveCamera(link, hdmi, run, may_open=a.allow, network=cam_network, screens=bool(address),
                             options=options, values=values, readings=readings, labels=known, look=look,
                             **({"owner": owner_cam} if owner_cam else {}))
            screens, ok = [], True
            opened = None           # on an address run, the frame a press opened a row on: from then MENU only
            owner_opened = False    # the owner row was opened once: never again this run
            try:
                # its one MENU through the one helper, and no second: drive.py sends what it is asked, and a menu that
                # did not open fails closed at find_position
                menu_from_shooting(cam, tries=0)
                j = find_position(cam, cycle, model)
                # the owner row's top-level row is gone to in the decision's own tab and group, and the page shown is
                # checked to be there before anything goes further (owner_place)
                there = {"place": owner_place[:2]} if owner_info else {}
                at = go_to(cam, cycle, model, j, a.path[0], **there) if j is not None else None
                if at is None:
                    raise NotReached(a.path[0])
                # the page model's row the scan went to, where it is the --path's one row, on an ordinary run: its
                # readings may tie a lit bar read with the row's icon as a letter or two to it, before any other press
                # (lit_refused, icon_reading)
                gone_to = scan_row(cycle, model, at) if (seen is not None and not a.network and not owner_info
                                                         and len(a.path) == 1) else None
                gone_to = (gone_to, other_names(model, a.path[0])) if gone_to else None
                if owner_info:
                    why = place_refused(screen_text(cam, a.grip), *owner_place[:2])
                    if why:
                        raise RuntimeError(f"--owner: {why}: nothing is opened (docs/decisions/0008)")
                if owner_info and len(a.path) > 1:
                    # each parent read before its Right, the page it opens read after it (owner_walk)
                    why = owner_walk(cam, a.path, a.grip, owner_place)
                    if why:
                        raise RuntimeError(f"--owner: {why}: nothing is opened (docs/decisions/0008)")
                else:
                    enter_any(cam, a.path, 0)
                if owner_info:
                    # from here the camera opens no row but the owner row, and takes no Enter outside it
                    # (LiveCamera.owner_only), whatever its lit text reads as
                    cam.owner_only = True
                depth = list(a.path[:-1])       # the labels above the menu page shown (next_depth)
                for i, p in enumerate(a.press):
                    # the key as the guards judge it and as it is sent (canonical_key; press_args_refused saw that
                    # every key is one)
                    key, y, want = parse_press(p)
                    last = i == len(a.press) - 1
                    later_enter = any(parse_press(q)[0] in ENTERS for q in a.press[i + 1:])
                    if opened and key != "menu":
                        # the address screen is open, whatever it reads as: nothing on it is chosen or scrolled
                        print(f"{key} refused: a row was opened on this address run ({opened}): no key but MENU goes "
                              "out on it (docs/decisions/0008); cancelling", flush=True)
                        run.log("press_refused", key=key, frame=cam.frame.path.name,
                                why="an address screen is open: no key but MENU")
                        ok = False
                        break
                    if inside and inside.get("owner") and y is not None:
                        print(f"{key} refused: inside the owner row no key@y is sent, only up, down, MENU and Enter; "
                              "cancelling", flush=True)
                        ok = False
                        break
                    if owner_info and not owner_opened and not inside and press_name(key) not in ("up", "down", "right"):
                        # between the walk to the owner row and its opening the page must stay the row's own place,
                        # which was read: Up and Down move the cursor, and Right, judged below, opens the row
                        print(f"{key} refused: between the walk to the owner row and its opening only Up and Down go "
                              "out, and Right opens it (docs/decisions/0008); cancelling", flush=True)
                        run.log("press_refused", key=key, frame=cam.frame.path.name,
                                why="before the owner row is opened, only up, down and its opening")
                        ok = False
                        break
                    if inside and not inside.get("owner"):
                        # a row a network decision opened is open, whatever its screen reads as: look only
                        why = inside_refused(key, cam, inside, options)
                        if why:
                            print(f"{key} refused: {say(why)}; cancelling", flush=True)
                            run.log("press_refused", key=key, frame=cam.frame.path.name, why=say(why))
                            ok = False
                            break
                    if y is not None:
                        t = screen_text(cam, a.grip) if want else ""
                        if want and not re.search(want, t, re.I):
                            print(f"the screen does not match {want!r}: {shown(t)[0]}; cancelling", flush=True)
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
                        print(f"the screen does not match {want!r}: {shown(t)[0]}; cancelling", flush=True)
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
                        print(f"Enter refused on the help popup: the cursor is on {say(repr(lit))}; cancelling", flush=True)
                        ok = False
                        break
                    # the owner row (--owner): what this press is there, judged here on this reading before the camera
                    # judges it on its own (LiveCamera): its opening, or a press inside it
                    owner_what, owner_opens, opening_row, kind_before = "", None, None, cam.read().kind
                    if owner_info and inside and inside.get("owner"):
                        why, owner_what = owner_press_decision(key, inside, owner_info,
                                                               lit if key in ENTERS else "", t, kind_now(), last,
                                                               a.confirm, later_enter)
                    elif owner_info and not inside and key in ENTERS + RIGHTS and lit and \
                            safety.owner_lifted_row(lit, owner_cam, values) is not None:
                        why, owner_what = owner_open_decision(key, lit, cam.read().kind, owner_label, owner_info, last,
                                                              a.confirm, owner_opened)
                        if not why:
                            # the page shown is the row's own place: its tab and group, or its parent's page
                            why = opening_place_refused(cam.read().kind, t, a.path, owner_place)
                        owner_opens = owner_label if not why else None
                    elif owner_info and key in ENTERS + RIGHTS:
                        # in an --owner run no Right or Enter goes that is not judged as the owner row's opening or a
                        # press inside it: a lit row misread ("Formal") is no ordinary row to open (2026-11-14, a review)
                        why = ("in an --owner run no Right or Enter goes out but the opening of the owner row and the "
                               f"presses inside it, and the lit row does not read as {owner_label!r} (docs/decisions/0008)")
                    elif not inside and key in OPENERS and cam.read().kind in ROW_PAGES_OPENED and seen is not None:
                        # a press that opens the lit row of a menu page: a row this camera has not been seen to open
                        # opens only as the --path's own last row (first_open_or_exit), never reached by the presses
                        decided = (safety.network_lifted_row(lit, cam_network, bool(address), values, readings, known)
                                   if a.network and lit else None)
                        why, opening_row = lit_refused(lit, depth, a.path, seen,
                                                       known_rows | set(shown_labels(cam, cycle, model)), decided,
                                                       row_vals, gone_to if i == 0 else None)
                    else:
                        why = ""
                    if why:
                        print(f"{key} refused: {say(why)}; cancelling", flush=True)
                        run.log("press_refused", key=key, frame=cam.frame.path.name, why=say(why))
                        ok = False
                        break
                    armed = owner_what in ARMED
                    # the owner route's --confirm covers only a press the owner gates judged a step or its armed press;
                    # without --owner nothing lifts every check
                    confirm_now = a.confirm and owner_what in ("step", *ARMED) if owner_info else False
                    # the text above the footer, where a question mark is judged (held vertically, or where it cannot be
                    # read alone, the whole text: the stricter)
                    body = None
                    if key in ENTERS and not a.grip:
                        try:
                            body = "" if getattr(cam, "blank", False) else body_of(cam)
                        except Exception:
                            body = None
                    # --confirm "SCREEN TEXT" (no --owner): one Enter, on that screen alone, past the shape check;
                    # --info-ok "ROW=PHRASE": the notice it names, its OK alone (enter_ways)
                    consent, notice_row, lone = enter_ways(cam, key, confirm_phrase if confirm_left else None,
                                                           named_notes, words=not private)
                    # this press is the --path's own first open on this body (first_open_or_exit), its RESTORE_BY_HAND
                    # written just before it goes: a look lap opens that never-open row under the procedure
                    first_intent = bool(first_label) and key in RIGHTS and not inside and reads_row(lit, first_label)
                    # on a look lap the camera is told the row a press opens only where it is the --path's last row:
                    # its label, whether its whole path is seen opened, whether its first open is under way
                    # (camkit.live.bar_is_row); any other opening press names no row (docs/decisions/0024)
                    target = ({"expected": (a.path[-1],), "seen": bool(seen is not None and seen.seen(a.path)),
                               "first": first_intent}
                              if look and key in OPENERS and opening_row is not None
                              and list(opening_row) == list(a.path) else None)
                    opening = {"row": target} if target else {}
                    why, vouched = press_decision(p, key, lit, t, cam.read().kind, confirm_now, a.allow, on_shooting,
                                                  network=cam_network, screens=bool(address), values=values,
                                                  readings=readings, owner=owner_cam,
                                                  armed_row=owner_label if armed else "", labels=known, body=body,
                                                  consent=consent,
                                                  notice_way=f"--info-ok {notice_row}" if notice_row else "", lone=lone,
                                                  look=look, row=target)
                    if vouched:
                        print(f"Enter vouched by the operator on {shown(t)[0]}", flush=True)
                    if why:
                        # on a notice (or a first-time screen) no --info-ok names: the flag that would, its text
                        # withheld on a --network or --owner run (live.info_ok_hint, which logs it in events.jsonl)
                        kind_now = cam.read().kind
                        hint = (f"; {info_ok_hint(cam, a.path[-1], cam.frame.path.name, info_ok_text(cam), not private)}"
                                if key in ENTERS and not notice_row and a.path
                                and (kind_now == "notice" or safety.first_time_screen(kind_now, t)) else "")
                        print(f"{key} refused: {say(why)}{hint}; cancelling", flush=True)
                        run.log("press_refused", key=key, frame=cam.frame.path.name, why=say(why))
                        ok = False
                        break
                    # the row this press opens, when a network decision opens it: from then on it is looked at only,
                    # until a MENU or an Enter on a named option (closes) brings back the page it is opened from now
                    opens = (safety.network_lifted_row(lit, cam_network, bool(address), values, readings, known)
                             if key in ENTERS + RIGHTS and lit and not inside and not owner_opens else None)
                    # a row a look lap opens, no decision naming it: looked at as a decided row with no option named,
                    # as the camera judges it (camkit.live.look_row); its bar as read ends the lock
                    look_bar = (look_row(lit, values, known, target)
                                if look and not opens and key in ENTERS + RIGHTS and lit and not inside
                                and not owner_opens and kind_before in ROW_PAGES_OPENED else None)
                    opened_from = cam.read() if opens or owner_opens or look_bar else None
                    closes = bool(inside) and key in CLOSES          # inside_refused let it through above
                    if owner_what in ("step", *ARMED):
                        # the camera presses it only with this word, for this row and this press (LiveCamera.permit)
                        cam.permit = {"row": owner_label, "what": owner_what}
                        print(f"   {key} inside {owner_label!r} as {owner_what}: the owner's decision and --confirm"
                              + (", as the run's last press" if armed else ""), flush=True)
                        run.log("owner_press", key=key, frame=cam.frame.path.name, row=owner_label, what=owner_what)
                    # a row's first open on this body (first_open_or_exit): its Right, on that very row, goes as an armed
                    # press that may drop the link
                    first_now = bool(first_label) and key in RIGHTS and not inside
                    # the bar read with the row's icon as a letter or two, which lit_refused tied to the --path's row
                    # (icon_reading), is that row too
                    tied = bool(gone_to) and i == 0 and opening_row is not None and list(opening_row) == list(a.path)
                    if first_now and not (owner_opens or opens or look_bar or reads_row(lit, first_label) or tied):
                        print(f"{key} refused: the lit row does not read {first_label!r}, whose first open this run makes; "
                              "cancelling", flush=True)
                        run.log("press_refused", key=key, frame=cam.frame.path.name, why="not the first open's row")
                        ok = False
                        break
                    if armed or first_now:
                        # a press that may drop the link (its decision's link_loss: safety.loses_link; a row's first
                        # open on this body): RESTORE_BY_HAND is written first (a), taken away when the press is refused
                        # before it goes (b), kept when anything else goes wrong (c), and then the screen read once
                        # decides (d, e, f)
                        may_lose = first_now or safety.loses_link(owner_label, owner_what)
                        handed = getattr(cam, "handed", 0)
                        if may_lose:
                            marker = intend_by_hand(run, before, owner_label, owner_entry, why=(
                                f"the first open of {' > '.join(a.path)!r} on this body may drop the link or act"
                                if first_now and not armed else ""))
                            byhand, first_went = "pending", first_now and not armed
                        try:
                            cam.press(key, **opening)          # once: no retry of an armed press
                        except (safety.Refused, StopRequested, CameraRefused):
                            if may_lose:            # (b) refused before it went, or "not accepted": nothing done
                                clear_restore_by_hand(run.root)
                                byhand, first_went = None, False
                            raise
                        except Exception as e:
                            if may_lose:            # (c) it may have gone: the marker stays, nothing more is pressed
                                byhand = "lost"
                                went = getattr(cam, "handed", 0) > handed
                                why_by_hand = (f"the press raised {type(e).__name__} after it was "
                                               f"{'handed to the link' if went else 'given to the camera'}")
                            raise
                        if inside:
                            inside["done"] = owner_what     # the run's one armed press went: MENU alone from here
                        if may_lose:
                            # a row's first open reads the option screens MENU leaves too; the owner route's armed
                            # press, SHOWN_KINDS alone
                            kind_after, t, why_not = after_armed(cam, a.grip, safety.FIRST_OPEN_KINDS
                                                                 if first_now and not armed else safety.SHOWN_KINDS)
                            frame_now = getattr(getattr(cam.frame, "path", None), "name", None)
                            entry = {"after": p, "frame": frame_now, "kind": kind_after,
                                     **({"armed": owner_what} if armed else {}),
                                     **({"first_open": True} if first_now else {})}
                            # kept as every screen of the owner row is, its opening's included: its field names and
                            # row labels, its text in drive.jsonl only where the decision logs values (owner_kept)
                            if why_not:
                                # (d) nothing after it can be judged: the marker stays, nothing more is pressed
                                byhand, why_by_hand = "lost", why_not
                                print(f"{p:32s} -> sent; {why_not}: nothing more is read or pressed", flush=True)
                            elif owner_info and safety.own_question(kind_after, t, owner_label):
                                # (e) the row's own question: nothing was done yet. MENU alone cancels it (never
                                # Enter); then the run restores as ever, and says nothing was confirmed
                                question = frame_now
                                entry.update(owner_kept(cam, a.grip, t, labels, told, owner_info, kind_after,
                                                        defined.get(owner_label, ()), by_row)[1])
                                print(f"{p:32s} -> {kind_after:9s} {frame_now}  the row's own question: nothing was "
                                      "confirmed; cancelling it with MENU, never Enter", flush=True)
                                run.log("armed_question", key=key, frame=frame_now, row=owner_label)
                                if cancel_question(cam, a.grip, owner_label):
                                    byhand = "question"
                                else:
                                    byhand, stuck = "lost", True
                                    why_by_hand = "its question was not seen gone after three MENUs"
                            else:
                                # (f) the link answered with another screen: MENU alone back to the shooting screen
                                # and the remote restore, the marker taken away only when the restore checks out
                                byhand = "answered"
                                console, kept = (owner_kept(cam, a.grip, t, labels, told, owner_info, kind_after,
                                                            defined.get(owner_label, ()), by_row)
                                                 if owner_info else shown(t))
                                entry.update(kept)
                                print(f"{p:32s} -> {kind_after:9s} {frame_now}  {console}", flush=True)
                            screens.append(entry)
                            break
                    elif key.startswith("dial."):
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
                        # an Enter judged here as the owner route's step or armed press: the camera's own check is lifted
                        # for it; one judged on the screen --confirm names: its shape check alone (answer), once; one on
                        # the notice --info-ok names: that notice's OK alone (notice_ok)
                        press(cam, key, confirm=bool(confirm_now and key in ENTERS), answer=consent or None,
                              **({"notice_ok": notice_row} if notice_row else {}),
                              **shooting_word(cam, run, key, on_shooting), **opening)
                        if consent:
                            confirm_left = 0            # --confirm lifts one Enter only
                            run.log("confirm_used", key=key, frame=cam.frame.path.name)
                        # on the help popup a Down can go unanswered: the cursor stayed on Add to My
                        # Menu in 4 of 8 drives (S&Q, 2026-11-02), 0.3 s or 1.3 s after C4 alike.
                        # Down again while the lit entry still reads Add to My Menu, at most twice
                        for _ in range(2):
                            if key != "down" or cam.read().kind != "helppop" or \
                                    not re.search(r"my menu", highlighted(cam.frame.image, cam.frame.path), re.I):
                                break
                            print("   the popup's cursor did not move: Down again", flush=True)
                            press(cam, "down")
                    if address and key in ENTERS + RIGHTS and not opened:
                        # whatever the screen it opened reads as (an address screen reads as no known kind)
                        opened = cam.frame.path.name
                        run.log("address_screen_opened", key=key, frame=opened)
                    t = screen_text(cam, a.grip)
                    depth = next_depth(depth, key, kind_before, opening_row, cam.read().kind)
                    if closes:
                        inside["closing"] = True
                    if owner_opens:
                        # the owner row: looked at from here (owner_press_decision), MENU alone from its opening where
                        # its values are withheld (blanked) or it is an address or serial number screen
                        cls = owner_info["class"]
                        blank = safety.blanked(cls, owner_info["logged"])
                        owner_opened = True
                        inside = {"row": owner_label, "class": cls, "address": cls == safety.LIFT_ADDRESS,
                                  "identity": blank or cls in (safety.LIFT_ADDRESS, safety.LIFT_SERIAL),
                                  "from": opened_from, "closing": False, "owner": True, "logged": owner_info["logged"],
                                  "blank": blank, "done": owner_what == "open"}
                        run.log("owner_row_opened", key=key, frame=cam.frame.path.name, row=owner_label,
                                lifted_from=cls, blank=blank)
                    elif opens:
                        cls = safety.lift_class(lit)
                        inside = {"row": opens, "class": cls, "address": cls == safety.LIFT_ADDRESS, "identity": False,
                                  "from": opened_from, "closing": False, "suspect": None}
                        run.log("network_row_opened", key=key, frame=cam.frame.path.name, row=opens, lifted_from=cls)
                    elif look_bar:
                        # named withheld in the logs: its bar can carry the row's value, the owner's; a credentials row
                        # is blanked from its opening, as the camera blanks it (safety.look_blank)
                        cls = safety.look_class(lit)
                        blank = any(safety.look_blank(x) for x in (lit, *safety.row_judged(lit, values, known)))
                        inside = {"row": WITHHELD_ROW, "bar": look_bar, "class": cls, "look": True, "blank": blank,
                                  "address": cls == safety.LIFT_ADDRESS, "identity": blank, "from": opened_from,
                                  "closing": False, "suspect": None}
                        run.log("network_row_opened", key=key, frame=cam.frame.path.name, row=WITHHELD_ROW,
                                lifted_from=cls, look=True, blank=blank)
                    elif inside:
                        # judged on this read alone, right after the closing key: the evidence is spent either way
                        if network_left(cam.read(), inside["from"], inside["closing"],
                                        highlighted(cam.frame.image, cam.frame.path) if inside["closing"] else "",
                                        inside.get("bar") or inside["row"], inside.get("suspect"),
                                        # the camera's own picture, into its own folder while a withheld row is open
                                        lambda: (cam.osd_seen() if hasattr(cam, "osd_seen")
                                                 else osd_kind(getattr(cam, "link", None))), readings, known):
                            run.log("network_row_left", key=key, frame=cam.frame.path.name, row=inside["row"])
                            inside = None
                        else:
                            inside["closing"] = False
                    if inside and cam.read().kind == "shooting" and inside.get("suspect") is None:
                        # the row still open and its screen read as the shooting screen: right after a MENU or a
                        # closing Enter, network_left would have ended the row on it, so no closing key has gone out
                        # since the row opened, and this is its own screen misread (Manage Paired Device's list,
                        # 2026-11-13). No key but MENU from here (kind_now)
                        inside["suspect"] = cam.read()
                        run.log("shooting_inside", key=key, frame=cam.frame.path.name, row=inside["row"])
                    if inside and not inside["identity"] and menu_only(inside, kind_now(), t):
                        # a pairing screen, a keyboard, credentials: MENU alone from here, its text never shown
                        inside["identity"] = True
                        run.log("identity_screen", key=key, frame=cam.frame.path.name)
                    console, kept = shown(t)
                    screens.append({"after": p, "frame": cam.frame.path.name, "kind": cam.read().kind, **kept,
                                    **({"vouched": True} if vouched else {}),
                                    **({"on_shooting": True} if shooting else {}),
                                    **({"armed": inside["done"]} if armed and inside and inside.get("done") else {}),
                                    **({"c4_allowed": True} if key in C4_OWNER_PRESSES else {})})
                    print(f"{p:32s} -> {cam.read().kind:9s} {cam.frame.path.name}  {console}", flush=True)
                if ok and not byhand:
                    time.sleep(a.wait)
                    cam.refresh("after-presses")
                    t = screen_text(cam, a.grip)
                    if inside and cam.read().kind == "shooting" and inside.get("suspect") is None:
                        # the row still open, whatever the last press was: failing closed, its field names alone
                        inside["suspect"] = cam.read()
                        run.log("shooting_inside", key="wait", frame=cam.frame.path.name, row=inside["row"])
                    if inside and not inside["identity"] and menu_only(inside, kind_now(), t):
                        inside["identity"] = True
                        run.log("identity_screen", key="wait", frame=cam.frame.path.name)
                    console, kept = shown(t)
                    screens.append({"after": "wait", "frame": cam.frame.path.name, "kind": cam.read().kind, **kept})
                    print(f"{'(after ' + str(a.wait) + ' s)':32s} -> {cam.read().kind:9s} {cam.frame.path.name}  {console}",
                          flush=True)
            except NotReached as e:
                # the row's name is the run's own argument: said as given, on every run; nothing read off the screen in
                # it (go_to's and find_position's own lines withhold what they read: crawl_run.said)
                print(f"error: {e}; cancelling", flush=True)
                ok, unreached = False, e.label
            except Exception as e:
                print(f"error: {say(f'{type(e).__name__}: {e}')}; cancelling", flush=True)
                ok = False
            if byhand and byhand not in ("question", "answered"):
                # the run's last press, an owner decision's "link_loss", may have gone and nothing after it can be
                # judged, or its question is still open: no cleanup press and no remote restore over it; the start file
                # goes back by hand, and no link opens before that (camkit.runs RESTORE_BY_HAND, docs/decisions/0015)
                log.write(json.dumps({"path": a.path, "presses": a.press, "note": a.note, "completed": ok,
                                      **({"owner": {owner_entry: {k: v for k, v in owner_info.items() if k != "why"}}}
                                         if owner_info else {}),
                                      **({"first_open": True} if first_label else {}),
                                      **({"network": dict(network)} if a.network else {}),
                                      "screens": screens, "before": before.name, "restore": "by hand",
                                      "outcome": ("question left open" if stuck else why_by_hand or "may have gone"),
                                      **({"question_frame": question} if question else {}),
                                      "marker": marker.name}) + "\n")
                log.flush()
                run.log("restore_by_hand", before=before.name, marker=str(marker), why=why_by_hand)
            else:
                # whatever ends the restore early (close giving up, a STOP while waiting, an upload refused) exits
                # EXIT_UNRESTORED (runner.restoring); after an armed press that may drop the link, the marker stays and
                # the run exits EXIT_RESTORE_BY_HAND instead. Either way drive.jsonl gets a result line saying so
                # (unfinished_line), where it was left empty (2026-11-14)
                result_written = False
                try:
                    with restoring("drive.py's restore", withhold=private):
                        close_for_restore(cam, link, before)
                        # the session's end every runner shares (runner.end_session): the shooting screen waited for
                        # (its playback view left with its Playback button once: runner.wait_shooting); a wait that
                        # gives up, a STOP or a first Ctrl-C meanwhile, or a link error there restores all the same over
                        # a screen that asks nothing, and over any other the owner clears it first (hold_for_owner);
                        # then the download, the diff, and the start file put back, before the log is written (a log
                        # that cannot be written skips nothing)
                        ending = end_session(link, hdmi, before, "the settings download after the presses",
                                             reach=functools.partial(wait_shooting, wait=wait_for),
                                             **(values_withheld(private) or {"show": 30}))
                        log.write(json.dumps({"path": a.path, "presses": a.press, "note": a.note, "completed": ok,
                                              **({"on_shooting": sorted(on_shooting)} if on_shooting else {}),
                                              **({"c4_allowed": c4_allowed} if c4_allowed else {}),
                                              **({"network": dict(network)} if a.network else {}),
                                              **({"address_screen": address} if address else {}),
                                              **({"owner": {owner_entry: {k: v for k, v in owner_info.items()
                                                                          if k != "why"}}} if owner_info else {}),
                                              **({"outcome": "question shown, cancelled", "question_frame": question}
                                                 if byhand == "question" else {}),
                                              **({"outcome": "pressed; the link answered", "marker": marker.name}
                                                 if byhand == "answered" else {}),
                                              **({"first_open": True} if first_label else {}),
                                              "screens": screens, "before": before.name,
                                              "after": ending.after.name if ending.after else None,
                                              "changes": changes_kept(ending.changes, keep_values)}) + "\n")
                        log.flush()
                        result_written = True
                except SystemExit:
                    if not result_written:
                        # the run's record: what it was asked to do and that it did not finish, never a screen's text;
                        # a log that cannot be written changes no exit status
                        with contextlib.suppress(OSError, ValueError):
                            log.write(json.dumps(unfinished_line(a, ok, before, network if a.network else None, address,
                                                                 owner_entry, owner_info, marker)) + "\n")
                            log.flush()
                    if not byhand:
                        raise
                    unfinished = True           # the marker stays (below)
        # while this run's own marker is there, the reconnection that checks the restore opens as
        # kit/tools/upload_check.py's does: to check that very start file (camkit.link pending_restore)
        checking = {"link_class": functools.partial(Link, pending_restore=True)} if byhand else {}
        restored = (False if byhand and (byhand not in ("question", "answered") or unfinished)
                    else restore_checked(run, ending, before, **checking, **values_withheld(private)))
    finally:
        hdmi.close()
        log.close()
        run.seal()          # a private run's folder checked owner-only, the eyes' polling target taken away
        ledger.after()      # one look into the coverage ledger's looks file; a failed write changes no exit status
    # a first open whose start file came back unchanged: the link answered and no record differed (camkit.first_open)
    first_changed = [c.key for c in ending.changes] if first_went and ending is not None else []
    if byhand in ("question", "answered") and restored and not first_changed:
        clear_restore_by_hand(run.root)
        run.log("restore_by_hand_cleared", outcome=byhand, frame=question)
        if first_went and byhand == "answered":
            print(f"the first open of {' > '.join(a.path)!r} on this body: the link held and no record differed from "
                  "the start file, so it opens as any row from now on", flush=True)
            return
        if byhand == "question":
            print(f"nothing was confirmed: the last press inside {owner_label!r} brought up its own question ({question}), "
                  "which MENU cancelled, and the start file is back and checked. The frame is the evidence that the "
                  "row opens to a question (docs/decisions/0005)", flush=True)
            sys.exit(EXIT_NOT_CONFIRMED)
        print(f"the last press inside {owner_label!r} went and the link still answered: the start file is back and "
              "checked (what no settings file holds, a network setup a reset wipes among it, is not)", flush=True)
        return
    if byhand and first_went:
        why = (f"{len(first_changed)} records then differed from the start file ({', '.join(first_changed[:8])}), "
               f"{'put back and checked' if restored else 'not put back and checked'}" if first_changed
               else "the restore after it did not check out" if byhand == "answered"
               else why_by_hand or "the link may have gone")
        print(first_open.owner_words([a.path], why, marker, before, run), flush=True)
        sys.exit(EXIT_RESTORE_BY_HAND)
    if byhand:
        why = ("its question was not seen gone after three MENUs: a person must cancel it on the camera (MENU or "
               "Cancel, never Enter)" if stuck
               else "the restore after it did not check out" if byhand in ("question", "answered")
               else why_by_hand or "it may have gone")
        print(f"the last press inside {owner_label!r} (the owner's decision says link_loss): {why}. {marker} names the "
              f"start file; no run opens a link until it is back. First look at the camera: whatever it still shows "
              f"(a question, a pairing, search or connection screen) is cancelled there by hand, with MENU or Cancel, "
              f"never Enter or OK. Once the camera is reachable again (by hand, as its owner sets it up), put the start "
              f"file back with\n  .venv/bin/python -u kit/tools/upload_check.py {run.dir.name}/dat/{before.name}\n"
              f"(docs/decisions/0015)", flush=True)
        sys.exit(EXIT_RESTORE_BY_HAND)       # the start file goes back by hand, once the link is back (exit_status)
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)
    if unreached is not None:
        # nothing was pressed on the row: a chain or an agent tells it from a run that did its presses (exit_status)
        print(f"{unreached!r} was not reached by the scan: its start file is back and checked, and none of the run's "
              f"presses went out on it (exit status {EXIT_INCOMPLETE})", flush=True)
        sys.exit(EXIT_INCOMPLETE)


if __name__ == "__main__":
    main()
