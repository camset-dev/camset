"""Find where each movable Focus Area keeps its frame's place: the area chosen, Stills slot 1 registered, the frame
moved with the multi-selector on the shooting screen, slot 1 registered again, the two downloads diffed (2026-11-09).

    .venv/bin/python -u kit/provers/framepos_run.py --list
    .venv/bin/python -u kit/provers/framepos_run.py --allow "Camera Set. Memory" [--areas "Zone,Spot: S"] [--limit N]
    .venv/bin/python -u kit/provers/framepos_run.py --allow "Camera Set. Memory" --areas "Custom 1" --moves "Right 1"
    .venv/bin/python -u kit/provers/framepos_run.py --allow "Camera Set. Memory" --grip down --areas "Zone,Custom 1"
    .venv/bin/python -u kit/provers/framepos_run.py --allow "Camera Set. Memory" --grip level --areas "Zone,Custom 1"
    .venv/bin/python -u kit/provers/framepos_run.py --summary            (the run's lines, deltas only; no camera)
    .venv/bin/python -u kit/provers/framepos_run.py --zone-grid --allow "Camera Set. Memory"     (the sweep only)
    .venv/bin/python -u kit/provers/framepos_run.py --zone-grid --grip down --allow "Camera Set. Memory"   (held so)
    .venv/bin/python -u kit/provers/framepos_run.py --allow "Camera Set. Memory" --edges [--areas "Spot: M"] [--grip down]
    .venv/bin/python -u kit/provers/framepos_run.py --allow "Camera Set. Memory" --put-back RUN    (a frame RUN left out)

The camera (the a1 II, firmware 4.00): moving a focus frame on the shooting screen changes no live record; registering
a memory slot copies its place into that slot's memory set (its hand tables,
data/ILCE-1M2_fw4.00/hand_tables_ILCE-1M2_fw4.00.json, ZONE and the point records' FRAME_PROOFS notes: the Zone's
place on its 3 x 3 grid in six records, the Spot point's X and Y on the 640 x 480 grid, 320, 240 the centre;
runs/<model>_fw<fw>/kit2_frame_reg registered nine zone places and two spot moves one by one). Which records the
other areas (Expand Spot, Custom 1-3, the Tracking areas) keep their place in is what this run finds.

--areas: labels as the definition's Focus Area values name them ("Spot: S", "Tracking: Custom 1"), comma-separated;
"default" (DEFAULT_AREAS, the default); or "all", every area whose frame moves. Wide and Center Fix (and their
Tracking forms) have no frame to move and are never planned. --list prints the plan and touches no camera. --summary
prints what the run's lines found, the changed keys with their deltas only.

--moves (2026-11-09): the presses that move a point or box area's frame in place of Left 3 and Up 2, comma-separated
in the order they are taken, each a direction (Left, Right, Up or Down, any case) and its presses, one to nine:
"Right 1", "Left 1,Up 1". A direction is given once and never with its opposite: the put-back is the moves reversed,
so Left with Right, or Up with Down, would only cancel. It is for a frame that stands near the limit of its travel,
which three Left presses can run into the limit: the delta is cut short, and as a press at the limit still counts as
taken, the put-back goes past where the frame was, which the check-back shows (the registration after the put-back
not matching the first). One press, or the other direction, may stay clear of the limit, and the check-back tells
whether it did (with --no-check-back nothing does, and the run says so). Zone and Tracking: Zone keep their own
one-step moves whatever --moves says, and --zone-grid its route (a plan of zones alone stops before anything
connects); their lines carry the context a run without --moves gives. The context names the moves ("moved Right 1"),
so a session under other moves keeps its own summary lines.

A run is bracketed as every run is (decision 15; runner.prover_session): the start download, then the setup through the
menu as kit/provers/afreg_run.py sets it (its functions, imported): Switch V/H AF Area = Off (the camera level: one
registration writes the three orientations' copies alike; --grip: AF Point + AF Area), and, when the plan holds a
Tracking area, Mode Dial Control Set's Drive Mode Dial = Set with Menu, Drive Mode = Single Shooting, its Focus Mode
Dial = Set with Menu and Focus Mode = Continuous AF (--drive-mode and --focus-mode as afreg_run has them).
--frame-move-amt Standard or Large sets AF Frame Move Amt (how far one press moves a frame) to that option by the menu
with these rows, before any move, and the context names it, so the step a press takes can be read from the deltas; the
download after the setup must hold the code the definition gives that option in AF Frame Move Amt's record
(amt_code), or the run stops before any area (the restore puts the setup back); leave (the default) keeps the camera's
own. Then per area:
  1. the area chosen in Focus Area's carousel and its second axis (afreg_run.choose_area), OK, the shooting screen;
     no recentring: the kit knows no press that recentres a frame, and the multi-selector's centre does on the shooting
     screen what the body's Custom Key assigns to it (a change the kit must not make, as C4 there: decision 7);
  2. slot 1 registered (register_slot) and a download, base-<area>;
  3. on the shooting screen, once the download's message has gone (afreg_run.ready_to_hold): the multi-selector's Left
     3 times and Up 2 times, or the presses --moves gives (Zone and Tracking: Zone, which step over a 3 x 3 grid: once
     each, whatever --moves says), every press read; a press the camera refuses, or one that brings a notice (waited
     out), is recorded and the run goes on;
  4. slot 1 registered again and a download, moved-<area>; the diff of the two is the area's place records;
  5. the frame put back: each move reversed, as many times as it was taken (Right and Down for Left and Up; Left and Up
     for a Right or Down --moves gave); with --check-back (the default) slot 1 registered a third time and a download,
     back-<area>, which must match base-<area>: the start file cannot put a frame back (no live record holds it), so
     this is how the run knows the owner's frame is where it was.
One line per area in the run's framepos.jsonl: {"area", "code", "moves", "sent", "put_back", "changed": [{"key",
"before", "after"}], "judged": [the delta of each, its axis by the definition's name, whether it went the way the
presses went: Left lowers X and Up lowers Y, Right and Down raise them; a grid record by its labels], "verdict",
"frames", "files", "back"}, tagged with the context and the allowance; a failed area's line says why.
framepos_summary.txt holds the summary, the last line of each area in each context (a run folder holding a Standard
and a Large session, or sessions under other --moves, keeps each), its head naming the context. Nothing a record held
is printed (decision 16): each changed key with its delta, and the count of records that differ at the end. Give a
--frame-move-amt run its own --run, and read a step's size only from an area whose put-back matched. A record family
the deltas show that the definition has no setting for gets no name from a run: map it with proofs first.

--zone-grid (2026-11-09): with Switch V/H AF Area = Off one Zone move writes the zone's grid index into every copy at
once (set1:0x019a, the level memories, the six vertical copies), so a sweep of the nine places proves the vertical
copies' nine values without turning the camera. The places' codes and names are the ZONE table of the hand tables of
the camera the kit works on (ZONE below), never another camera's: a camera whose tables name none stops before
anything connects. After the same setup, Zone chosen, slot 1 is registered and downloaded
(zone-start) and the start place read from set1:0x019a; the frame is led to the upper left by exact presses (Left
column+1 times, Up row+1 times: none goes past an edge, so the route holds whether the zone stops at an edge or wraps;
kit2_frame's notes do not say which), then Right, Right, Down, Left, Left, Down, Right, Right, slot 1 registered and a
download (zone-<place name>) at each, the place read from the download and checked against the route (a place that
reads otherwise stops the sweep); the frame put back where it started and registered once more (zone-back), which must
match zone-start. One line a place in zone_grid.jsonl: {"place" (code), "name", "expected", "confirmed", "download",
"records" (every set1 record that changed to the code), "groups" (them by orientation: zone_group)}; one proof line
a (record, code) in proofs.jsonl for the current record and the six vertical copies (kind "registration mirror", as
memreg_run.py), written only once the place reads as routed (a place that reads otherwise writes its zone_grid.jsonl
line and no proof line), applied when the record changed to the code from the download before (one that holds the
code unchanged may hold the camera's own place), its base that download (the place before, or zone-start for the
first; the run of 2026-11-09 named zone-start for every place, which kit/tools/replay_proofs.py allows: it checks what
the record holds after); the run is marked as one of the camera's proof runs (camkit.runs.PROOF_RUN), so
kit/pass2_report.py's mirrored_values hands the places to kit/schema_update.py, which names them proved. Alone the
flag runs the sweep only; with --areas the sweep first, then those areas. Codes, names and keys are all it prints: the
start place and the presses that put the frame back (which tell it) stay in the run's files, except when the frame
cannot be put back or the run stops with it moved: then the presses owed are printed, so the owner can finish by hand.
A place that does not read as routed ends the walk: what the keys did is said (a step's own move from a place that read
as routed; the presses toward the corner only as having led elsewhere, as they tell the start), with the turns and
mirrors of the level keys that explain every move seen (zone_fits), and the zone is put back and checked all the same; a
zone-back off its start is brought there straight once under the one mapping the walk showed (the level one where every
place read as routed, after a press lost on the way back) and checked again, never under a guess.

--zone-grid --grip down|up (2026-11-17): the same sweep held vertically, with the grip runs' setup (Switch V/H AF Area
= AF Point + AF Area, and Circ. of Focus Point = Does Not Circulate so a zone stops at an edge), Zone chosen and the
screens read as the grip runs read them (Vertical Display from the start download), the lines carrying their context
("..., camera grip down, Vertical Display On"), "grip" and "upright". Each place's line names what its registration
wrote by orientation (zone_group: the records every orientation writes, 0x019a, 0x0f0b and 0x0f0d, and that grip's
copies) and any zone record that took another code ("other"). Its proof lines are the level sweep's kind, "registration
mirror", for the records a registration held that way writes (sweep_records: the every-orientation records and the
grip's own copies), each applied only where the record changed to the place's code: pass2_report.mirrored_values reads
no context, and schema_update credits a value under the table's own label only, so they add the codes the level sweep
proved and can contradict nothing; a copy that took a code of its own is credited nothing and shows in "other". The
keys are not assumed to move the zone as level: the route check says what a place read as.

--grip down|up (2026-11-15): the owner holds the camera vertically for the whole run, as afreg_run.py's --grip
(orient_run.py's plumbing): the setup puts Switch V/H AF Area on AF Point + AF Area, so a registration writes that
orientation's copies, and the run shows which. Held vertically the camera draws the shooting screen and the dialogs
opened from the menu in their portrait arrangement, which HDMI shows turned a quarter and the SDK's picture unturned
but squeezed into its 640 x 480; the menu pages, the slot screen and its "Registered." stay level (kit2_vertical, held
grip up, read them level). So Focus Area's dialog is read made upright (afreg_run.choose_area; orient_run.upright turns
HDMI's frame back and resizes the SDK's), the shooting screen's words around the moves likewise as afreg_run.hold_fn
reads its message (afreg_run.shooting_words: the download's message waited out by ready_to_hold, a notice a press
brings), and its kind judged as level (the turned shooting screen reads as the shooting screen: kit/tests/test_core.py's
turned screens). A check the turned screen does not let the run make stops
it, saying which and why: a screen not read as the shooting screen before a press, or a shooting screen whose upright
reading holds no text (the camera perhaps held the other way); with a grip any area that fails ends the run, its frame
put back first. The presses are the level ones (or --moves), but their directions are not taken to map onto X and Y:
no delta is judged against them (the verdict counts the records that changed), and each area's summary names every
changed record by its definition key and the definition's name with its delta, then one line "grip down writes:
<names>": the diff whole, never filtered to one orientation's copies. The lines carry the context ("Switch V/H AF Area
= AF Point + AF Area, camera grip down"), "grip" and "upright": true. --zone-grid takes --grip down or up (below);
with --grip level it is refused, the level sweep being made with Switch V/H AF Area Off; a plan that would open Drive
Mode's chooser held vertically (a Tracking area) is refused without --drive-mode leave, that chooser being drawn in the
portrait arrangement, which the kit cannot read. Vertical Display, read from the start download
(afreg_run.screens_held, 2026-11-16), decides what turns: Off keeps every screen level, so each is read as a level run
reads it and the lines carry no "upright"; On, or not read, is the above, the portrait shooting screen the SDK's
picture shows read as it is (camkit.screen.portrait_battery). The context ends "camera grip down, Vertical Display Off"
or "..., Vertical Display On" as the start download holds it, nothing added where it was not read.

--grip level (2026-11-15): the same setup with the camera standing level, so a registration writes the level copies
alone, proved directly rather than by elimination from the two vertical holds; every screen is read, and the frame
moved and put back, as a level run does, and failed areas end the run as a level run's do (three in a row). Its lines
carry the context "Switch V/H AF Area = AF Point + AF Area, camera level" and "grip": "level" (no "upright"), and each
area's summary ends "level writes: <names>". No record of the a1 II says how the camera is held (0x04e2, once taken
for one, held the same level and vertical, 2026-11-16): what a registration wrote, which the summary names, is how a
run shows the camera was held as the grip says.

--edges (2026-11-16): how far each movable frame can travel, for an editor that offers the places a frame can take.
Every movable area but the zones (their places are the nine --zone-grid proves; named in --areas they are refused), or
the areas --areas names. The setup adds Circ. of Focus Point = Does Not Circulate (a frame that wraps round at an edge
has none to find) and AF Frame Move Amt = Standard unless --frame-move-amt says otherwise, both checked in the download
after the setup. Per area (edge_area), each step registered and downloaded: the start (base); pushed --edge-presses
Left and Up to the low corner (low); Right 1 (snap-h: the records Right moves are those that changed); Right 1 and Down
1 (step-h: Right's step; the records Down moves); Down 1 and Right pushed (step-v: Down's step, the far horizontal
edge); Down pushed (high, the far corner). Which key moves which record is measured, never taken from a name, so a view
that turns the keys is no guess. The single presses are read once they settle (press_moves); the pushes are sent
quickly, each judged at the link on a fresh frame read as the shooting screen (push). What the registrations of
2026-11-16 show (axis_way): a press moves a whole step, the first off an edge too, under Standard and Large alike, and
stops at an edge; under Standard a press that would cross the centre between a record's edges stops on it (each way back
from the far corner to a start at the centre landed on it, where whole steps would have passed it by up to a step;
kit2_framepos_amt's Custom 1 too: Left 3 from the centre met the edge, Right 3 came back to the centre); under Large none
did (kit2_a1fin_framepos_edges_gripup_large_plain crossed it three times). All those starts were the centre, and every
crossing seen went Left or Up. So the way back is made under Standard (edge_way_back): from the far corner, whole steps
where it does not cross the centre, as many presses as reach the centre or an edge, across the centre to it and on in
whole steps; registered and checked against the start's registration record by record (AF Frame Move Amt's own records
left out); a landing still off is planned again from there, EDGE_TRIES times at most; a start no press reaches is said
with the difference, nothing more pressed, and the run stops. Under --frame-move-amt Large the measure is Large's and
the way back Standard's: AF Frame Move Amt = Standard through its row once the far corner is registered, the presses
counted in Standard's step (the hand tables' FRAME_STEPS, refused before anything connects where they give none), Large
again before the next area, whose start must read Large. A failure once the frame has moved closes the screen, measures
again on the low side what is not yet known, pushes the frame to the far corner and brings it back from there under
Standard. A push that moved its whole length may have stopped short of the edge: said, the frame brought back all the
same. Seven
registrations an area: about five minutes, an hour and a half for the 18 areas (edge_minutes; the pushed presses not
yet timed). One line an area in edges.jsonl ({"area", "code", "edge_presses", "files", "frames", "values" (each
registration's place records: the run's own evidence, the start among them), "edges" (edge_records), "odd", "back":
{"same", "off", "tries", "presses"}, "failed", "moved"}) and edges_summary.txt: each record's edges, step and first
press off the corner, by key and the definition's name, never the start nor the presses, which tell it. Edges are
camera facts for the hand tables' FRAME_TRAVEL, copied there by hand (docs/DATA_CONTRACTS.md: no kit step writes them;
the runs go into the hand evidence, and kit/writer/frames.py puts the table on the definition): a run file,
not proofs.jsonl, which holds the values a record was proved to take; and they are an area's, where the definition's
range and step are a record's, which areas of several sizes share (the Spot sizes). A Custom box's edges are those of
the size its owner set (a setting of theirs), never a camera fact as they stand.

--put-back RUN (2026-11-16): each frame an --edges run left out of place (left_behind: its last line says it moved and
is not back) brought back to that run's start registration, held as that run held the camera (its lines' grip;
Vertical Display read from this run's start download), the setup putting Switch V/H AF Area as the grip has it, Circ. of
Focus Point and AF Frame Move Amt Standard. Per area (put_back_area): chosen; slot 1 registered where the frame is now;
at its start already, nothing pressed; else pushed Right and Down to the far corner, registered, brought back from
there as an edges run's way back is, in Standard's step (FRAME_STEPS), each landing registered and checked on the
measured records alone (the start's file holds the edges run's AF Frame Move Amt). A start no press reaches is said
with the difference and the run stops; a failure leaves the frame where it is, and a run again starts from wherever that
is. Lines in put_back.jsonl; the same consent as --edges. An area a STOP ended once its frame moved has its line
written all the same (stopped_line: "stopped", no "back", its registrations so far); one a run stopped in before
2026-11-17, which wrote none, is found from the run's files (files_lines: its edge-base download no line names, its
state the line before it or setup.jsonl). Such an area is planned from its registrations alone (files_m: the records
that changed, X or Y by name, Right and Down raising them level, Standard's step, the grid's centre). The place grid is
stretched over the recorded picture, so a start off the centre (320, 240) is put back only where the camera's start
download reads the Aspect Ratio its own start download did (ratio_refusal), else refused, nothing pressed.

Movie and S&Q (2026-11-17): a run works in the mode its --scan was made in (scan_for; Stills for the default, the
latest Stills scan), so a Stills run stops on a camera kit/provers/mode_switch.py --keep left in Movie, and a run on a
Movie page scan goes on there. Such a run plans Focus Area from that mode's crawl (mode_map: kit2_crawl_movie; --map
names another), leaving out and saying the areas the mode does not offer (Movie and S&Q: no Tracking area); it registers
slot 1 of that mode's memory, the camera section's memory_sets (the a1 II's Movie Memory 1, memory set 4; in S&Q, S&Q
Memory 1 or Time-lapse Memory 1, set 7 or 10, as the start download's S&Q Shoot Mode says), which must be filled in the
start file, its records the restore check leaves out; the setup leaves out, and says, a row the mode does not offer
(Switch V/H AF Area), and stops where it needs one (Drive Mode). The context begins "Movie mode, camera level", and the
lines carry "mode" and "memory_set". --grip and --zone-grid stay Stills' (both rest on Switch V/H AF Area).

Registering: MENU, Camera Set. Memory by the page scan, its lit row read as that row, Enter; the slot screen (its tabs 1
2 3 M1-M4, slot 1 lit by default, its footer OK) must read as one (SLOT_SCREEN), and its lit tab must be slot 1,
measured on the frame (lit_slot: kit2_small_1109's 00021_enter.png and kit2_frame_reg's 00079-00081, slots 1-3, 60 px
apart); a lit tab elsewhere is stepped to slot 1 with Left. Enter then goes as drive.py's enter!:REGEX does
(drive.press_decision: nothing on the screen never-open, no confirmation), and "Registered." must follow. Camera Set.
Memory is a never-open action row (camkit.safety): the run opens it only when given --allow "Camera Set. Memory", the
owner's word, and says so in every line ("allowance"). Registering also writes slot 1's three registration records,
set1:0x023c (filled), set1:0x11ab (the family) and set1:0x11ad (the exposure mode), which no settings file sets back:
the session's end and its restore check say them by key and leave them out (runner.prover_session's expected, as
kit/provers/memreg_run.py has it, EXPECTED_LEFT); any other difference is a restore that did not take (exit
EXIT_UNRESTORED). For the same reason a run whose start file has slot 1 empty stops before its first press: registering
it would mark it filled for good.
"""
import argparse
import contextlib
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parent))
import afreg_run  # noqa: E402
from afreg_run import bare, setting_code, slug  # noqa: E402,F401 (setting_code: this module's name for it too)
from camkit import definitions, jsonl, paths, safety  # noqa: E402
from runner import (LATEST_SCAN, add_allow_argument, add_info_ok_argument, add_scan_argument, allowed_or_exit,  # noqa: E402
                    notes_named_or_exit, read_json)
from writer import hand_tables  # noqa: E402

# the Zone grid's places, [code, name], of the camera the kit works on (its hand tables' ZONE, writer/hand_tables.py:
# the public table alone); empty for a camera whose tables name none, where --zone-grid stops before the camera
ZONE = hand_tables.active().ZONE
# each area's step a press under AF Frame Move Amt Standard and Large, {(option, area): (x, y)}, of the camera the kit
# works on (its hand tables' FRAME_STEPS): a Large edge measure's way back counts in Standard's (standard_step)
FRAME_STEPS = hand_tables.active().FRAME_STEPS
ROW = "Focus Area"
MEMORY_ROW = "Camera Set. Memory"
VH_ROW, OFF = "Switch V/H AF Area", "Off"
AMT_ROW = "AF Frame Move Amt"               # how far one press moves a frame: Standard or Large (--frame-move-amt)
DEFAULT_AREAS = ("Zone", "Spot: S", "Spot: M", "Spot: L", "Spot: XL", "Spot: XS", "Expand Spot", "Custom 1", "Custom 2",
                 "Custom 3", "Tracking: Zone", "Tracking: Spot M", "Tracking: Expand Spot", "Tracking: Custom 1")
FIXED = ("Wide", "Center Fix")              # no frame to move (and their Tracking forms)
MOVES = (("ms_left", 3), ("ms_up", 2))     # one step a press (the a1 II); the control wheel's keys are never pressed there
ZONE_MOVES = (("ms_left", 1), ("ms_up", 1))     # Zone steps over its 3 x 3 grid
BACK = {"ms_left": "ms_right", "ms_right": "ms_left", "ms_up": "ms_down", "ms_down": "ms_up"}
PULL = {"ms_left": ("x", -1), "ms_right": ("x", 1), "ms_up": ("y", -1), "ms_down": ("y", 1)}
WORDS = {"ms_left": "Left", "ms_right": "Right", "ms_up": "Up", "ms_down": "Down"}
KEYS = {w.lower(): k for k, w in WORDS.items()}         # --moves: a direction's word, any case, to its key
EDGES = {"ms_left": "left", "ms_right": "right", "ms_up": "top", "ms_down": "bottom"}     # where a press runs a frame
NOTICE_S = 6.0                              # how long a notice over the shooting screen gets to go by itself
# slot 1's registration records, which no settings file sets back (docs/models/ILCE-1M2_fw4.00.md, Camera Set. Memory;
# kit2_small_1109's 00159_restored.DAT and 00289_restored.DAT); the first is the filled mark, 4 once registered
EXPECTED_LEFT = ("set1:0x023c", "set1:0x11ab", "set1:0x11ad")
FILLED = ("set1:0x023c", 4)
# the slot screen: "MR Memory 1 2 3 M1 M2 M3 M4" over the settings the slot would take (kit2_small_1109 00021_enter.png)
SLOT_SCREEN = re.compile(r"\bmemory\b[\s\S]*\bm[1-4]\b", re.I)
# its tabs, 60 px apart along the top: slot 1's lit tab spans x 224-273, slot 2's 284-333, slot 3's 344-393 (kit2_frame_reg
# 00079-00081_right.png; 00021, 00154 and 00282 of kit2_small_1109 and kit2_afpoint's 00049 alike), in y 4-52
SLOT_TABS = ("1", "2", "3", "M1", "M2", "M3", "M4")
TAB_BAND, TAB_FIRST, TAB_PITCH = (4, 52), 248.5, 60
# a zone grid record's labels as places (column, row): left and up are negative (the definition's ZONE values)
PLACES = {"centre": (0, 0), "center": (0, 0), "up": (0, -1), "right": (1, 0), "left": (-1, 0), "down": (0, 1),
          "lower right": (1, 1), "lower left": (-1, 1), "upper left": (-1, -1), "upper right": (1, -1)}
# --zone-grid: the nine places of the Zone's 3 x 3 grid, visited row by row from the upper left (Right, Right, Down,
# Left, Left, Down, Right, Right), slot 1 registered and a download at each
SWEEP_STEPS = (None, "ms_right", "ms_right", "ms_down", "ms_left", "ms_left", "ms_down", "ms_right", "ms_right")
ZONE_CURRENT = "set1:0x019a"                    # the Zone place in the current set: names the place in each download
PROOF_KIND = "registration mirror"              # the kind memreg_run.py gives a registration's proof lines
MAP_WORDS = "pass 1's map"                      # the Stills map a plan routes by (kit2_pass1/map_all.json)
# a zone record's orientation, as its name says: written in every orientation (no orientation in its name: the current
# record and the level memories), horizontal, vertical grip down or grip up
GROUPS = ("every orientation", *afreg_run.GROUPS)
# --grip: level stands the camera level with each orientation kept apart; down and up hold it vertically, where the
# shooting screen and the dialogs turn (TURNED: read upright as afreg_run reads them)
GRIPS, TURNED = ("level", "down", "up"), ("down", "up")
VH_OPTION = {None: afreg_run.VH[None], "level": afreg_run.VH["down"], "down": afreg_run.VH["down"], "up": afreg_run.VH["up"]}
# --edges: Circ. of Focus Point (a frame at an edge jumping to the far one) put on its option that stops it, as the
# definition's values name them (the a1 II's global:0x03a1: Does Not Circulate 0, Circulate 1)
CIRC_ROW, CIRC_OFF = "Circ. of Focus Point", "Does Not Circulate"
# the 640 x 480 grid's centre, X and Y by the records' names: every frame's edges lie either side of it alike, at every
# Aspect Ratio (the grid is stretched over the recorded picture, so a place off it has other numbers at another ratio:
# Custom 3's Y 194-286 at 16:9, 201-279 at 3:2, 2026-11-17)
GRID_CENTRE = {"X": 320, "Y": 240}
RATIO_ROW = "Aspect Ratio"
EDGE_PRESSES = 40           # a push's presses: past the widest travel the smallest step crosses (Spot XS: 32 across 640)
EDGE_TRIES = 3              # registrations after the first way back that may make good a press the camera lost
PUSH_GAP = 0.35             # s between a push's presses, none waited on to settle (not yet timed on the camera)
# an edge measure's registrations, in order: the start; the low corner (Left and Up pushed); Right 1 off it; Right 1 and
# Down 1 more; Down 1 more and Right pushed (the far edge); Down pushed (the far corner)
EDGE_TAGS = ("base", "low", "snap-h", "step-h", "step-v", "high")
# how long an area takes: a registration with its download and the menu lock (kit2_a1fin_framepos_level, 2026-11-16:
# 17.5 s), choosing an area, a press read once it settles (6.5 s: the shooting screen's blinking keeps the settle from
# ending early) and a pushed press (PUSH_GAP and a frame read)
REG_S, CHOOSE_S, SETTLED_S, PUSHED_S = 18, 45, 6.5, 0.6


# ---------------------------------------------------------------- the plan, from the definition (no camera)

def fixed(label: str) -> bool:
    """An area with no frame to move: Wide, Center Fix, and their Tracking forms."""
    base = label.split(":", 1)[1] if label.startswith("Tracking:") else label
    return bare(base) in {bare(x) for x in FIXED}


def gridded(label: str) -> bool:
    """A zone area (Zone, Tracking: Zone), whose frame steps over a 3 x 3 grid."""
    return bare(label).endswith("zone")


def parse_moves(text: str) -> list:
    """[[key, presses]] of --moves ("Right 1", "Left 1,Up 1"), in the order given: each a direction (Left, Right, Up or
    Down, any case) and one to nine presses, comma-separated; a direction once, never with its opposite (the put-back
    is the moves reversed, so Left with Right, or Up with Down, would only cancel); at least one move. Any other value
    ends the run before anything connects, saying what is wrong."""
    def bad(why):
        sys.exit(f"framepos_run: --moves {text!r}: {why}")
    out = []
    for part in (x.strip() for x in str(text).split(",")):
        if not part:
            continue
        m = re.fullmatch(r"([A-Za-z]+)\s+([0-9]+)", part)
        if not m:
            bad(f"{part!r} is not a direction and its presses ('Right 1')")
        key = KEYS.get(m.group(1).lower())
        if key is None:
            bad(f"{m.group(1)!r} is not a direction: Left, Right, Up or Down")
        n = int(m.group(2))
        if not 1 <= n <= 9:
            bad(f"{n} {WORDS[key]} presses: a direction takes one to nine")
        if any(k == key for k, _ in out):
            bad(f"{WORDS[key]} is given twice: a direction once")
        if any(k == BACK[key] for k, _ in out):
            bad(f"{WORDS[BACK[key]]} with {WORDS[key]}: the put-back is the moves reversed, so the two would only cancel")
        out.append([key, n])
    if not out:
        bad("no move: a direction and its presses, comma-separated ('Right 1', 'Left 1,Up 1')")
    return out


def moves_of(label: str, moves: list | None = None) -> list:
    """[(key, presses)] that move an area's frame: `moves` (--moves, as parse_moves reads it) or Left 3 and Up 2; once
    each for a zone (Zone, Tracking: Zone), whatever `moves` says."""
    return [list(m) for m in (ZONE_MOVES if gridded(label) else (moves or MOVES))]


def back_of(done: list) -> list:
    """The presses that put the frame back: each move taken, reversed, as many times as it was taken."""
    return [[BACK[k], n] for k, n in reversed(done) if n]


def left_to_send(moves: list, done: list) -> list:
    """The presses of `moves` not yet taken, `done` being [(key, presses taken)] in their order, cut short where a
    failure stopped them."""
    out = []
    for i, (k, n) in enumerate(moves):
        rest = n - (done[i][1] if i < len(done) else 0)
        if rest:
            out.append([k, rest])
    return out


def plan(doc: dict, areas: str = "default", moves: list | None = None) -> list:
    """[{"label", "code", "moves", "tracking"}] for the areas asked for: "default" (DEFAULT_AREAS, in that order), "all"
    (every area of the definition's Focus Area values whose frame moves, in their order), or labels, comma-separated,
    in the order given; `moves` (--moves) for every area but a zone (moves_of). A label not offered, or one whose frame
    cannot move, stops the plan."""
    values = [(code, label) for code, label in afreg_run.records(doc, "horizontal")["area"].get("values") or []]
    if areas == "all":
        chosen = [x for x in values if not fixed(x[1])]
    else:
        asked = list(DEFAULT_AREAS) if areas == "default" else [x.strip() for x in areas.split(",") if x.strip()]
        unknown = [x for x in asked if not any(bare(lab) == bare(x) for _, lab in values)]
        if unknown or not asked:
            sys.exit(f"framepos_run: --areas {areas!r}: {unknown or 'nothing'} not among {[lab for _, lab in values]}")
        still = [x for x in asked if fixed(x)]
        if still:
            sys.exit(f"framepos_run: --areas {areas!r}: {still} have no frame to move (Wide, Center Fix): not planned")
        chosen = []
        for x in asked:
            hit = next(v for v in values if bare(v[1]) == bare(x))
            if hit not in chosen:
                chosen.append(hit)
    return [{"label": lab, "code": code, "moves": moves_of(lab, moves), "tracking": lab.startswith("Tracking")}
            for code, lab in chosen]


# ---------------------------------------------------------------- the shooting mode (no camera)

def run_mode(scan) -> str:
    """The shooting mode a run works in: the one its page scan records (runner.recorded_mode: a Movie scan's run works
    in Movie), Stills for the latest scan (--scan's default is Stills') and for a scan that records none (made before
    scans recorded it, all Stills')."""
    from runner import recorded_mode
    return "Stills" if str(scan) == LATEST_SCAN else recorded_mode(Path(str(scan))) or "Stills"


def scan_for(scan):
    """--scan's value with the mode the run works in (run_mode), as prove_run, pass3 and scale_run take a mode from
    their scan; runner.scan_dir then refuses a run while the kit's record says the camera was left in another mode (a
    Stills run on a camera mode_switch.py --keep left in Movie), and a Movie run goes on there."""
    from runner import in_mode
    return in_mode(scan, run_mode(scan))


def mode_map(mode: str, root: Path | None = None, path: list | None = None) -> str | None:
    """The map a run in `mode` plans Focus Area from (or the row at `path`: mode_switch.list_labels' File Format in
    Movie): None for Stills (pass 1's, kit2_pass1/map_all.json); for another mode a crawl of it, kit2_crawl*/map.json
    whose name names the mode (kit2_crawl_movie, kit2_crawl_sq; as kit/tools/proof_viewer.py's walk_frames and
    menu_tree.py --mode read them), the plainest name first among those whose map has the row; None where none has it."""
    import json
    if mode == "Stills":
        return None
    root = Path(root) if root is not None else paths.run_root(required=False)
    if root is None or not root.is_dir():
        return None
    word = re.sub(r"[^a-z0-9]+", "", mode.lower())
    crawls = sorted((p.parent for p in root.glob("kit2_crawl*/map.json")
                     if word in [w for w in p.parent.name[len("kit2_crawl"):].split("_") if w]),
                    key=lambda c: (len(c.name), c.name))
    for crawl in crawls:
        try:
            rows = json.loads((crawl / "map.json").read_text(encoding="utf-8")).get("rows") or []
        except (OSError, ValueError, AttributeError):
            continue
        if any(r.get("path") == (list(path) if path else [ROW]) for r in rows):
            return str(crawl / "map.json")
    return None


def map_labels(mp, path: list) -> list | None:
    """The labels of the row `path` in the map `mp`, in its options' order, each once (a grid's options indexed by [row,
    column], as Focus Area Limit's are); None where the map has no such row or cannot be read."""
    import json
    try:
        rows = json.loads(Path(mp).read_text(encoding="utf-8")).get("rows") or []
    except (OSError, ValueError, AttributeError):
        return None
    row = next((r for r in rows if r.get("path") == path), None)
    if row is None:
        return None
    out = []
    for o in row.get("options") or []:
        if o.get("label") not in out:
            out.append(o.get("label"))
    return out


def offered(todo: list, labels: list, axes: dict, limit: list | None) -> tuple:
    """(kept, left out) of a plan for a mode whose map is not Stills': an area the mode offers is one its map's Focus
    Area Limit grid names (`limit`: every area the mode has, Movie's no Tracking area), or, without that row, one the
    map's carousel and the axis walk route (afreg_run.route)."""
    if limit is not None:
        names = {bare(x) for x in limit}
        keep = [t for t in todo if bare(t["label"]) in names]
    else:
        keep = [t for t in todo if afreg_run.route(t["label"], labels, axes or {}) is not None]
    return keep, [t for t in todo if t not in keep]


def scan_rows(scan) -> list:
    """[(row, its page's group)] of a page scan's page model (model.json), each row as it keeps its readings; [] where it
    cannot be read."""
    import json

    from crawl_run import page_group
    try:
        pages = json.loads((Path(str(scan)) / "model.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [(r, page_group(p)) for p in pages if isinstance(p, dict) for r in p.get("rows") or [] if isinstance(r, dict)]


def absent_rows(mode: str, index: dict, rows: list, wanted: list) -> dict:
    """{row: why} of the setup rows `wanted` that shooting mode `mode` does not offer: the definition's record the row
    writes gives other modes (afreg_run.row_in_mode: Switch V/H AF Area's "still image"), or the mode's page scan
    (`rows`, scan_rows) holds no row of that name (crawl_run's go_to finds a row so: page_model.same_text, or
    crawl_run.row_named). Stills: none, its setup as it always was."""
    if mode == "Stills":
        return {}
    from crawl_run import row_named
    from page_model import same_text
    out = {}
    for row in wanted:
        modes = (afreg_run.row_record(index, [row]) or {}).get("modes")
        if afreg_run.row_in_mode(index, [row], mode) is False:
            out[row] = f"the definition gives it {modes} only"
        elif not any(same_text(r.get("label") or "", row) or row_named(r, row, g) for r, g in rows):
            out[row] = f"{mode} mode's page scan has no such row"
    return out


def run_set(a, index: dict, start) -> int:
    """The memory set this run registers: a.memory_set (main: the mode's first, memory_set; slot 1's set 1 for a run
    that names none); in S&Q, whose switch position holds S&Q Motion and Time-lapse with memories of their own, the one
    the start download's family names (sq_family): S&Q Memory 1, or Time-lapse Memory 1. Failed where the family cannot
    be read or the definition numbers no set for it."""
    from prove_run import Failed
    if getattr(a, "mode", "Stills") != "S&Q":
        return getattr(a, "memory_set", None) or 1
    family = sq_family(index, start)
    n = memory_set({"camera": {"memory_sets": getattr(a, "memory_sets", None) or {}}}, family) if family else None
    if n is None:
        raise Failed("which S&Q family the camera is in (S&Q Motion or Time-lapse, whose memories differ) could not be "
                     "read from the start download, or the definition numbers no memory set for it: nothing registered")
    return n


def slot_words(doc: dict, mode: str, n: int | None) -> tuple:
    """(the slot in words, its registration records' keys in words) for the plan: Stills' "slot 1" and EXPECTED_LEFT;
    another mode's by the camera section's names ("Movie Memory 1 (memory set 4)"); S&Q's two families both, the start
    download deciding."""
    if mode == "Stills":
        return "slot 1", ", ".join(slot_records(n or 1))
    if n is None:
        sq, tl = memory_set(doc, "S&Q"), memory_set(doc, "Time-lapse")
        if not tl:
            return f"{memory_name(doc, sq)} (memory set {sq})", ", ".join(slot_records(sq))
        return (f"{memory_name(doc, sq)} (memory set {sq}; {memory_name(doc, tl)}, memory set {tl}, where the start "
                "download has S&Q Shoot Mode on Time-lapse)",
                f"{', '.join(slot_records(sq))} ({memory_name(doc, tl)}'s: {', '.join(slot_records(tl))})")
    return f"{memory_name(doc, n)} (memory set {n})", ", ".join(slot_records(n))


def memory_set(doc: dict, mode: str) -> int | None:
    """The settings file section of shooting mode `mode`'s first memory slot, which the run registers: the camera
    section's memory_sets.modes (the a1 II's Stills 1, Movie 4, S&Q 7, Time-lapse 10); None where it names none."""
    got = (((doc.get("camera") or {}).get("memory_sets") or {}).get("modes") or {}).get(mode)
    return got[0] if got else None


def memory_name(doc: dict, n: int) -> str:
    """A memory set by the camera section's name for it ("Movie Memory 1"), else "memory set <n>"."""
    return (((doc.get("camera") or {}).get("memory_sets") or {}).get("names") or {}).get(str(n)) or f"memory set {n}"


def sq_family(index: dict, cs) -> str | None:
    """Which family S&Q is in, as the settings file `cs` (the start download) holds it, by the definition's one record
    whose values are S&Q Motion and Time-lapse (the a1 II's global:0x118b): "S&Q" or "Time-lapse", whose memories
    differ (memory_sets.modes); None where no record, or several, says it, or the file holds neither."""
    from prove_run import held_value
    hits = [s for k, s in index.items() if k.startswith("global:")
            and {str(lab) for _, lab in s.get("values") or []} == {"S&Q Motion", "Time-lapse"}]
    if len(hits) != 1:
        return None
    label = {v: lab for v, lab in hits[0]["values"]}.get(held_value(cs, hits[0]["key"]))
    return {"S&Q Motion": "S&Q", "Time-lapse": "Time-lapse"}.get(label)


def slot_records(n: int = 1) -> tuple:
    """Memory set `n`'s registration records, which no settings file sets back (EXPECTED_LEFT is Stills' set 1)."""
    return tuple(f"set{n}:{k.split(':', 1)[1]}" for k in EXPECTED_LEFT)


def setup_steps(focus: bool, drive: bool, amt: str | None = None, grip: str | None = None, circ: bool = False,
                vh: bool = True) -> list:
    """[(kind, text)] the setup in order, as afreg_run.setup_steps names them: "dial" (a Mode Dial Control Set cell put
    on Set with Menu), "drive" (Drive Mode = Single Shooting), "row" (a list row: "path = option"); Switch V/H AF Area
    Off, or AF Point + AF Area with any grip, level too (VH_OPTION), unless `vh` is False (Movie and S&Q, whose menus
    offer no such row); Circ. of Focus Point = Does Not Circulate with circ (--edges); AF Frame Move Amt last, when amt
    names its option."""
    steps = [("dial", afreg_run.DRIVE_DIAL), ("drive", f"{afreg_run.DRIVE_ROW} = {afreg_run.SINGLE}")] if drive else []
    if focus:
        steps += [("dial", afreg_run.FOCUS_DIAL), ("row", f"{afreg_run.FOCUS_ROW} = {afreg_run.CONTINUOUS}")]
    return (steps + ([("row", f"{VH_ROW} = {VH_OPTION[grip]}")] if vh else [])
            + ([("row", f"{CIRC_ROW} = {CIRC_OFF}")] if circ else []) + ([("row", f"{AMT_ROW} = {amt}")] if amt else []))


def setup_rows(amt: str | None = None, grip: str | None = None, circ: bool = False) -> dict:
    """{a "row" step's text, as setup_steps names it: (the row's menu path, the option)}, AF Frame Move Amt's when amt
    names its option, Switch V/H AF Area's as the grip has it, Circ. of Focus Point's with circ."""
    rows = {f"{afreg_run.FOCUS_ROW} = {afreg_run.CONTINUOUS}": ([afreg_run.FOCUS_ROW], afreg_run.CONTINUOUS),
            f"{VH_ROW} = {VH_OPTION[grip]}": ([VH_ROW], VH_OPTION[grip])}
    return (rows | ({f"{CIRC_ROW} = {CIRC_OFF}": ([CIRC_ROW], CIRC_OFF)} if circ else {})
            | ({f"{AMT_ROW} = {amt}": ([AMT_ROW], amt)} if amt else {}))


def amt_code(index: dict, amt: str) -> tuple | None:
    """(key, code): AF Frame Move Amt's live record in the definition and the code its values give the option `amt`
    (setting_code: the a1 II's global:0x03a3, Standard 0 and Large 1, proved by the menu in pass 2, kit2_pass2); None
    when the definition has no such record, or its values do not name the option."""
    return setting_code(index, [AMT_ROW], amt)


def context_of(extra: str | None, amt: str | None = None, moves: list | None = None, grip: str | None = None,
               vertical: str | None = None, mode: str = "Stills") -> str:
    """The state the registrations are made in, which every line carries and the summary keeps apart: the camera level
    with Switch V/H AF Area Off, or with a grip AF Point + AF Area and how the camera stands (held vertically in
    afreg_run's words, afreg_run.context_of: "Switch V/H AF Area = AF Point + AF Area, camera grip down", and ",
    Vertical Display Off" or ", Vertical Display On" as the start download holds it, `vertical`; level, "..., camera
    level", as the hand tables' ORIENTED reads it), AF Frame Move Amt when the run sets it, the moves when --moves gave
    them ("moved Right 1"), then --context. In Movie or S&Q (`mode`), whose menus offer no Switch V/H AF Area, "Movie
    mode, camera level" in its place, a --context saying no more than that mode left out."""
    if mode != "Stills":
        held = f"{mode} mode, camera level"
        extra = None if extra and extra.strip().lower() == f"{mode} mode".lower() else extra
    else:
        held = (f"{VH_ROW} = {VH_OPTION[grip]}, camera level" if grip == "level" else
                afreg_run.context_of(grip, None, vertical) if grip else f"{VH_ROW} {OFF}, camera level")
    base = held + (f", {AMT_ROW} {amt}" if amt else "") + (f", moved {say_moves(moves)}" if moves else "")
    return f"{base}, {extra}" if extra else base


def turned_of(grip: str | None, vertical: str | None = None) -> str | None:
    """The grip whose screens turn (down, up), as afreg_run's readers take it; None level, with --grip level too, and
    held vertically with Vertical Display Off (`vertical`), which keeps every screen level (afreg_run.turned_of)."""
    return afreg_run.turned_of(grip, vertical)


def held_words(grip: str) -> str:
    """How a grip holds the camera, as its summary says it: "level", "grip down", "grip up"."""
    return "level" if grip == "level" else f"grip {grip}"


def sweep_words() -> str:
    """The sweep in words for --list: Zone chosen, the start registered and downloaded, the frame led to the upper left
    corner by exact presses (from the place the start download reads), the nine places row by row, put back."""
    steps = ", ".join(WORDS[k] for k in SWEEP_STEPS if k)
    names = ", ".join(place_name(p) for _, p in sweep_route())
    return (f"Zone chosen; slot 1 registered and downloaded at the start (zone-start), its place read from the download; "
            f"the frame led to the upper left by exact presses (Left and Up as many as its column and row call for); then "
            f"{steps}, slot 1 registered and a download (zone-<place>) at each: {names}; each place read from "
            f"{ZONE_CURRENT} and checked against the route; put back where it started, registered and downloaded once "
            f"more (zone-back); zone_grid.jsonl and proofs.jsonl written")


def say_moves(moves: list) -> str:
    return ", ".join(f"{WORDS[k]} {n}" for k, n in moves) or "none"


def step_words(moves: list) -> str:
    """The deltas the step a press takes is read from, for --list: "X over 3 Left presses, Y over 2 Up presses", X
    first; an axis no move is on is left out."""
    said = {PULL[k][0]: f"{PULL[k][0].upper()} over {n} {WORDS[k]} press{'es' if n != 1 else ''}" for k, n in moves}
    return ", ".join(said[x] for x in ("x", "y") if x in said)


# ---------------------------------------------------------------- judging a diff (no camera)

def def_key(key: str) -> str:
    """A diff's key as the definition keys a set's records ("set1:0x019c" -> "set:0x019c")."""
    return re.sub(r"^set\d+:", "set:", key)


def axis_of(name) -> str | None:
    """X or Y when the definition's name says which ("AF point position X (current)"), else None."""
    m = re.search(r"\b([XY])\b", name or "")
    return m.group(1) if m else None


def place_of(label) -> tuple | None:
    """A zone grid label's place (column, row), or None."""
    return PLACES.get(" ".join(str(label or "").lower().split()))


def pull_of(done: list) -> dict:
    """{"x": presses right less presses left, "y": presses down less presses up} of the moves taken."""
    out = {"x": 0, "y": 0}
    for k, n in done:
        axis, step = PULL[k]
        out[axis] += step * n
    return out


def sign(n) -> int:
    return (n > 0) - (n < 0)


def judged(changes: list, index: dict, done: list) -> list:
    """Each changed record as the presses explain it: {"key", "name", "axis", "kind", ...}. kind "grid" (a record whose
    definition labels both values as zone places: "grid" [columns, rows] moved), "scalar" ("delta", and "per_press"
    when the name gives the axis) or "values" (a record of several values: "values" [{"i", "delta"}] of those that
    changed). "with_presses": whether it moved the way the presses went (Left lowers X and Up lowers Y, Right and Down
    raise them; a record whose axis the name does not give, either way the presses went), None when the presses say
    nothing of it. `index`: the definition's settings by key; `done`: [(key, presses taken)]."""
    p = pull_of(done)
    sx, sy = sign(p["x"]), sign(p["y"])
    out = []
    for c in changes:
        s = index.get(def_key(c["key"])) or {}
        name, b, a = s.get("name"), c["before"], c["after"]
        axis = axis_of(name)
        item = {"key": c["key"], "name": name, "axis": axis}
        if isinstance(b, list) or isinstance(a, list):
            b, a = list(b) if isinstance(b, list) else [b], list(a) if isinstance(a, list) else [a]
            # one record's two values have one length (a diff compares one layout); a shorter one is compared as far
            # as it goes
            item.update(kind="values", with_presses=None,
                        values=[{"i": i, "delta": y - x} for i, (x, y) in enumerate(zip(b, a, strict=False)) if x != y])
            out.append(item)
            continue
        labels = {v: lab for v, lab in s.get("values") or []}
        pb, pa = place_of(labels.get(b)), place_of(labels.get(a))
        if pb and pa:
            dc, dr = pa[0] - pb[0], pa[1] - pb[1]
            ok = None if not (sx or sy) else (sign(dc) in (0, sx) and sign(dr) in (0, sy) and (dc, dr) != (0, 0))
            item.update(kind="grid", grid=[dc, dr], with_presses=ok)
        else:
            d = a - b
            want = {"X": {sx}, "Y": {sy}}.get(axis, {sx, sy}) - {0}
            item.update(kind="scalar", delta=d, with_presses=(sign(d) in want) if want else None)
            n = abs(p["x"]) if axis == "X" else abs(p["y"]) if axis == "Y" else 0
            if n:
                item["per_press"] = round(d / n, 2)
        out.append(item)
    return out


def taken_ways(done: list) -> list:
    """The directions the verdict words, X first: Left and Up when those two were asked (the default moves, a zone's,
    or --moves "Left 1,Up 1"), whichever of them was taken, as always; else exactly the directions taken (a refused one
    left out), so a verdict never names an axis or a direction no press went."""
    asked = {k for k, _ in done}
    if asked == {"ms_left", "ms_up"}:
        return ["ms_left", "ms_up"]
    return sorted({k for k, n in done if n} or asked, key=lambda k: (PULL[k][0], k))


def verdict(items: list, done: list, grip: str | None = None) -> str:
    """The area's verdict in words. With a grip the presses' directions are not taken to map onto X and Y: it counts
    the records that changed and judges no direction."""
    if not any(n for _, n in done):
        return ("no press was taken (each refused or answered by a notice)"
                + (f"; yet {len(items)} records changed" if items else ": nothing to judge"))
    if grip:
        return (f"{len(items)} record{'s' if len(items) != 1 else ''} changed" if items else
                "nothing changed: the frame did not move (it sat at an edge already), or no record the registration "
                "writes holds its place")
    ways = taken_ways(done)
    if not items:
        edges = " and ".join(EDGES[k] for k in ways) + (" edges" if len(ways) > 1 else " edge")
        return (f"nothing changed: the frame did not move (it sat at the {edges} already), or no record "
                "the registration writes holds its place")
    against = [i["key"] for i in items if i["with_presses"] is False]
    went = sum(1 for i in items if i["with_presses"] is True)
    several = sum(1 for i in items if i["kind"] == "values")
    rule = ", ".join(f"{WORDS[k]} {'raises' if PULL[k][1] > 0 else 'lowers'} {PULL[k][0].upper()}" for k in ways)
    out = f"{went} record{'s' if went != 1 else ''} moved the way the presses went ({rule})"
    if against:
        out += f"; {len(against)} the other way ({', '.join(against)})"
    if several:
        out += f"; {several} record{'s' if several != 1 else ''} of several values changed"
    return out


def area_line(t: dict, changes: list, index: dict, sent: list, done: list, put_back: list, frames: dict, files: dict,
              back_changes: list | None = None, grip: str | None = None, upright: bool | None = None) -> dict:
    """The area's line for framepos.jsonl: the changes as the diff gives them (before and after: the run's own evidence,
    kept in runs/ alone), how each is judged and the verdict; "back" says whether the registration after the put-back
    matched the first (None without --check-back). With a grip each change is judged against no press (its delta only)
    and the line carries "grip", and "upright" when the screens were read turned (`upright`; by default as the grip
    turns them: down, up), as afreg_run's proof lines do."""
    items = judged(changes, index, [] if grip else done)
    upright = bool(turned_of(grip)) if upright is None else upright
    line = {"t": round(time.time(), 3), "area": t["label"], "code": t["code"], "moves": t["moves"], "sent": sent,
            "taken": done, "put_back": put_back, "changed": changes, "judged": items,
            "verdict": verdict(items, done, grip), "frames": frames, "files": files,
            **({"upright": True} if upright else {}), **({"grip": grip} if grip else {})}
    if back_changes is not None:
        line["back"] = {"same": not back_changes, "off": judged(back_changes, index, [])}
    return line


def said_delta(item: dict) -> str:
    """One judged record in words, its delta only."""
    if item["kind"] == "grid":
        return f"grid {item['grid'][0]:+d} column(s), {item['grid'][1]:+d} row(s)"
    if item["kind"] == "values":
        vals = item["values"]
        shown = ", ".join(f"[{v['i']}] {v['delta']:+d}" for v in vals[:6])
        return f"{len(vals)} of its values changed: {shown}{', ...' if len(vals) > 6 else ''}"
    per = f" ({item['per_press']:+g} a press)" if "per_press" in item else ""
    return f"{item['delta']:+d}{per}"


def shown_key(key: str, n: int = 1) -> str:
    """A changed key as a grip run's summary names it: a record of the memory set the run registers (`n`: slot 1's set
    1, Movie Memory 1's set 4) by its definition key (def_key), any other as the diff gives it."""
    return def_key(key) if key.startswith(f"set{n}:") else key


def summary_of(line: dict) -> list:
    """The area's lines of the summary: what moved, by key and delta only (never a value a record held). A grip line's
    keys are definition keys (shown_key), and one line "grip down writes: <names>" ("level writes:" for --grip level)
    names every record that changed by the definition's name (one it does not name by its key)."""
    head = f"{line['area']} (code {line.get('code')}" + (f"; {line['context']})" if line.get("context") else ")")
    if line.get("failed"):
        return [f"{head}: failed: {line['failed']}"]
    grip, n = line.get("grip"), line.get("memory_set", 1)
    out = [f"{head}, {say_moves(line['moves'])} asked, {say_moves(line.get('taken') or [])} taken: {line['verdict']}"]
    for i in line.get("judged") or []:
        mark = "  [the other way]" if i["with_presses"] is False else ""
        key = shown_key(i["key"], n) if grip else i["key"]
        out.append(f"    {key}  {i['name'] or '(not in the definition)'}: {said_delta(i)}{mark}")
    if grip:
        names = [i["name"] or shown_key(i["key"], n) for i in line.get("judged") or []]
        out.append(f"    {held_words(grip)} writes: {'; '.join(names) or 'nothing'}")
    notes = [f"{'put back, ' if x.get('put_back') else ''}{WORDS.get(x['key'], x['key'])} "
             + (f"refused ({x['refused'][:60]})" if x.get("refused") else f"answered by a notice ({x['frame']})")
             for x in line.get("sent") or [] if x.get("refused") or x.get("notice")]
    if notes:
        out.append("    presses: " + "; ".join(notes))
    if line.get("put_back_short"):
        out.append(f"    PUT BACK SHORT: on the shooting screen with {ROW} = {line['area']}, press "
                   f"{say_moves(line['put_back_short'])} by hand")
    back = line.get("back")
    if back is None:
        out.append(f"    put back: {say_moves(line.get('put_back') or [])} (not checked)")
    elif back["same"]:
        out.append(f"    put back: {say_moves(line.get('put_back') or [])}; the registration after it matched the first")
    else:
        off = "; ".join(f"{x['key']} {said_delta(x)}" for x in back["off"])
        out.append(f"    put back: {say_moves(line.get('put_back') or [])}; NOT where it was: {off} off: move it back "
                   "by hand")
    return out


def summary_lines(lines: list) -> list:
    """The summary of a run's lines, the last line of each area in each context (a step run's Standard and Large
    sessions both), in the order they came; each area's head names its context (summary_of)."""
    last = {}
    for ln in lines:
        if ln.get("area"):
            key = (ln["area"], ln.get("context"))
            last.pop(key, None)
            last[key] = ln
    return [s for ln in last.values() for s in summary_of(ln)]


def slot_filled(cs, n: int = 1) -> bool:
    """Slot 1 registered already in a settings file (its filled mark, FILLED, in memory set `n`: Stills' 1, Movie's 4 on
    the a1 II): registering an empty one would mark it filled for good, since no settings file empties it."""
    from prove_run import held_value
    key, code = FILLED
    return held_value(cs, f"set{n}:{key.split(':', 1)[1]}") == code


# ---------------------------------------------------------------- the zone grid sweep (no camera)

def zone_names(table=None) -> dict:
    """{code: name} of the Zone grid table (`table`, else the camera's hand tables' ZONE)."""
    return {int(c): n for c, n in (ZONE if table is None else table)}


def code_place(code, table=None) -> tuple | None:
    """A grid code's place (column, row), left and up negative, or None for a code the table does not name."""
    return place_of(zone_names(table).get(code))


def place_name(place: tuple, table=None) -> str | None:
    """The table's name for a place (column, row), or None."""
    for _, n in (ZONE if table is None else table):
        if place_of(n) == tuple(place):
            return n
    return None


def corner_moves(place: tuple) -> list:
    """The presses from a place to the upper left corner, counted exactly (Left as many times as the column is right of
    the left edge, Up likewise): none goes past an edge, so they are right whether the zone stops at an edge or wraps."""
    c, r = place
    return [[k, n] for k, n in (("ms_left", c + 1), ("ms_up", r + 1)) if n]


def net_back(done: list) -> list:
    """The fewest presses that undo everything in `done` ([key, presses taken], any order)."""
    p = pull_of(done)
    return [[k, n] for k, n in (("ms_left" if p["x"] > 0 else "ms_right", abs(p["x"])),
                                ("ms_up" if p["y"] > 0 else "ms_down", abs(p["y"]))) if n]


def sweep_route() -> list:
    """[(step, place)] the nine places in the order visited: step None for the first (the upper left corner), then the
    key pressed to reach each, and the place (column, row) it should be."""
    out, at = [], (-1, -1)
    for k in SWEEP_STEPS:
        if k:
            dx, dy = {"ms_right": (1, 0), "ms_left": (-1, 0), "ms_down": (0, 1), "ms_up": (0, -1)}[k]
            at = (at[0] + dx, at[1] + dy)
        out.append((k, at))
    return out


def zone_group(name) -> str:
    """The orientation group of a zone record by the definition's name (GROUPS): "vertical, grip down" or "vertical,
    grip up" where the name says the grip ("Zone position memory (vertical, grip down, grid index, copy 1)"),
    "horizontal" where it says horizontal, else "every orientation" (the current record and the level memories, which
    a registration writes however the camera is held)."""
    n = name or ""
    return GROUPS[2] if "grip down" in n else GROUPS[3] if "grip up" in n else GROUPS[1] if "horizontal" in n \
        else GROUPS[0]


def holders(changes: list, code) -> list:
    """The set1 records that changed to `code` between two downloads (keys; a record of several values is left out)."""
    return [c["key"] for c in changes if c["key"].startswith("set1:") and not isinstance(c["after"], list)
            and c["after"] == code]


def groups_of(keys: list, index: dict) -> dict:
    """{group: [keys]} of the records, by the definition's names (def_key); the four groups always present, and "not in
    the definition" for a record it does not name."""
    out = {g: [] for g in GROUPS}
    for k in keys:
        name = (index.get(def_key(k)) or {}).get("name")
        out.setdefault(zone_group(name) if name else "not in the definition", []).append(k)
    return out


def zone_records(index: dict) -> list:
    """The zone grid records the sweep proves, as definition keys ("set:0x0f32"): the six vertical copies and the
    current record, found by their names in the definition."""
    return sorted(k for k, s in index.items() if k.startswith("set:") and "Zone position" in (s.get("name") or "")
                  and "grid index" in s["name"] and ("vertical" in s["name"] or "(current" in s["name"]))


def sweep_records(index: dict, grip: str | None = None) -> list:
    """The zone records a sweep's proof lines cover: level (no grip, Switch V/H AF Area Off), zone_records; held
    vertically (grip down or up, AF Point + AF Area), the records every orientation's registration writes (the current
    record and the level memories: no orientation in their names) and that grip's own copies, never the other grip's nor
    the horizontal copies, which its registrations do not write."""
    if grip not in TURNED:
        return zone_records(index)
    own = GROUPS[2] if grip == "down" else GROUPS[3]
    return sorted(k for k, s in index.items() if k.startswith("set:") and "Zone position" in (s.get("name") or "")
                  and "grid index" in s["name"] and zone_group(s["name"]) in (GROUPS[0], own))


# how the multi-selector's keys may move the zone on its grid held vertically: each of the eight turns and mirrors of
# the level keys, as (what Right does, what Down does) in (columns, rows); level, Right moves it right and Down down
KEY_MAPS = (((1, 0), (0, 1)), ((0, 1), (-1, 0)), ((-1, 0), (0, -1)), ((0, -1), (1, 0)),
            ((-1, 0), (0, 1)), ((1, 0), (0, -1)), ((0, 1), (1, 0)), ((0, -1), (-1, 0)))
WAYS = {(1, 0): "right", (-1, 0): "left", (0, 1): "down", (0, -1): "up"}


def key_vector(key: str, mapping: tuple) -> tuple:
    right, down = mapping
    return {"ms_right": right, "ms_left": (-right[0], -right[1]), "ms_down": down, "ms_up": (-down[0], -down[1])}[key]


def zone_moved(place: tuple, presses: list, mapping: tuple) -> tuple:
    """A zone's place after `presses` ([[key, n]]) under a key mapping, each press stopped at the grid's edge (Circ. of
    Focus Point = Does Not Circulate, which a vertical sweep sets)."""
    c, r = place
    for key, n in presses:
        dc, dr = key_vector(key, mapping)
        for _ in range(n):
            c, r = max(-1, min(1, c + dc)), max(-1, min(1, r + dr))
    return c, r


def zone_fits(place: tuple, presses: list, read: tuple) -> list:
    """The key mappings (KEY_MAPS) under which `presses` from `place` lead to `read`, the level one first."""
    return [m for m in KEY_MAPS if zone_moved(place, presses, m) == tuple(read)]


def mapping_words(mapping: tuple) -> str:
    """A key mapping in words: "as level" for the level keys, else what Right and Down did."""
    if mapping == KEY_MAPS[0]:
        return "as level (Right moved it right, Down down)"
    return f"Right moved it {WAYS[mapping[0]]}, Down {WAYS[mapping[1]]}"


def zone_back_presses(now: tuple, start: tuple, mapping: tuple) -> list:
    """The presses that bring a zone from `now` to `start` straight (no edge in the way: both lie on the grid) under a
    key mapping: as many Right (or Left) presses as the move's share along Right's way, likewise Down."""
    dc, dr = start[0] - now[0], start[1] - now[1]
    right, down = mapping
    kr, kd = dc * right[0] + dr * right[1], dc * down[0] + dr * down[1]
    return [[k, abs(n)] for k, n in (("ms_right" if kr > 0 else "ms_left", kr), ("ms_down" if kd > 0 else "ms_up", kd))
            if n]


def sweep_line(k: int, expected: tuple, code, base_changes: list, download: str, index: dict, table=None) -> dict:
    """The place's line for zone_grid.jsonl: {"place" (the code read from the download), "name" (the table's), "expected"
    (the place the route led to), "confirmed", "download", "records" (every set1 record that changed to the code),
    "groups" (them by orientation, zone_group), "other" (each zone record, by the definition's name, that changed to
    another code: {key: code}, a copy that took a place of its own)}; no value but the codes."""
    name = zone_names(table).get(code)
    keys = holders(base_changes, code)
    other = {c["key"]: c["after"] for c in base_changes if c["key"].startswith("set1:") and c["key"] not in keys
             and not isinstance(c["after"], list) and "Zone position" in ((index.get(def_key(c["key"])) or {})
                                                                         .get("name") or "")}
    return {"t": round(time.time(), 3), "n": k + 1, "place": code, "name": name, "expected": place_name(expected, table),
            "confirmed": name is not None and code_place(code, table) == tuple(expected), "download": download,
            "records": keys, "groups": groups_of(keys, index), "other": other}


def sweep_proofs(line: dict, held: dict, base: str, changes: list, index: dict, tag: dict,
                 grip: str | None = None) -> list:
    """One proof line per zone record (zone_records) for the place: applied only when the place reads as the route led
    (line["confirmed"]), the record holds the place's code and it changed to it from the download before (it is among
    line["records"]). An unconfirmed place's download may still hold the start place, and a record that holds the code
    without changing may hold what the camera had, so neither is credited: a put-back by another name (decision 16).
    `held`: {definition key: value in the place's download}; `changes`: the diff from the previous download. Held
    vertically (`grip` down or up) the records are sweep_records' for that grip, and a copy that took a code of its own
    is credited nothing (it does not hold the place's code)."""
    code, out = line["place"], []
    state = (f"{VH_ROW} = {VH_OPTION[grip]}, the camera held {held_words(grip)}" if grip in TURNED
             else f"{VH_ROW} = {OFF}")
    for rec in sweep_records(index, grip):
        key = rec.replace("set:", "set1:", 1)
        ch = [c for c in changes if c["key"] == key]
        why = None if line.get("confirmed") else "the place does not read as the route led there"
        if why is None and held.get(rec) != code:
            why = "the record does not hold the place's code"
        if why is None and key not in (line.get("records") or ()):
            why = "the record did not change to the place's code: what it holds may be the camera's own"
        applied = why is None
        out.append({"path": [MEMORY_ROW, "Zone place"], "menu": MEMORY_ROW, "kind": PROOF_KIND, "record": rec, "key": key,
                    "index": code, "label": line["name"],
                    "via": f"Focus Area = Zone with {state}, the frame moved with the multi-selector to the "
                           f"{line['name']} place, then slot 1 registered ({MEMORY_ROW}, Enter on the slot)",
                    "slot": "1", "base": base, "dat": line["download"], "after": line["download"], "changes": ch,
                    "applied": applied, **({} if applied else {"not_applied": why}), **tag})
    return out


def place_written(run_dir: Path, line: dict, held: dict, base: str, changes: list, index: dict, tag: dict,
                  grip: str | None = None) -> list:
    """A place of the sweep written: its line in zone_grid.jsonl always (confirmed or not), and its proof lines
    (sweep_proofs, for `grip`'s records) in proofs.jsonl, the run marked as a proof run, only once the place reads as the
    route led (line["confirmed"]): an unconfirmed place writes no proof line. Returns the proof lines written."""
    from camkit.runs import mark_proof_run
    jsonl.append(run_dir / "zone_grid.jsonl", dict(line, **tag))
    if not line.get("confirmed"):
        return []
    got = sweep_proofs(line, held, base, changes, index, tag, grip)
    for p in got:
        jsonl.append(run_dir / "proofs.jsonl", p)
    mark_proof_run(run_dir, "kit/provers/framepos_run.py --zone-grid")     # the writer reads these lines
    return got


# ---------------------------------------------------------------- the edges (no camera)

def edge_plan(doc: dict, areas: str | None) -> list:
    """--edges's plan: every area whose frame moves but the zones (no --areas, "default" or "all"), or the labels given
    (plan); a zone asked for by name stops the plan before anything connects: Zone and Tracking: Zone step over the
    nine named places --zone-grid proved, whose edges are the grid's own."""
    if areas in (None, "default", "all"):
        return [t for t in plan(doc, "all") if not gridded(t["label"])]
    todo = plan(doc, areas)
    zones = [t["label"] for t in todo if gridded(t["label"])]
    if zones:
        sys.exit(f"framepos_run: --edges: {zones} step over the nine named places --zone-grid proved: their edges are "
                 "the grid's own, nothing to measure")
    return todo


def edge_groups(regs: dict) -> dict:
    """{"h": keys, "v": keys}: the records the horizontal keys move, those that changed when Right alone was pressed off
    the low corner (regs "low" to "snap-h"), and the vertical keys', those that changed when Down joined it ("snap-h" to
    "step-h"), less the first: measured, never taken from a record's name or from how a view turns. `regs`: {tag:
    {key: value}} by EDGE_TAGS."""
    h = [k for k in regs["low"] if regs["snap-h"].get(k) != regs["low"].get(k)]
    v = [k for k in regs["snap-h"] if regs["step-h"].get(k) != regs["snap-h"].get(k) and k not in h]
    return {"h": h, "v": v}


def centre_of(low, high) -> int | None:
    """The middle of a record's two edges, where a Standard press that would cross it stops (every frame's edges lie
    either side of it alike: kit2_a1fin_framepos_edges_level, 2026-11-16); None where it falls between two values."""
    return None if low is None or high is None or (low + high) % 2 else (low + high) // 2


def edge_measure(regs: dict, n: int) -> dict:
    """{"h": axis, "v": axis, "odd": keys} of an edge measure's registrations (`regs`, EDGE_TAGS; `n`: a push's
    presses). Each axis: "keys" (edge_groups), "step" (by key: the second press off the low edge, signed for Right or
    Down), "first" (the first press off it, signed: a whole step in every run, Standard and Large alike, kept to show
    it), "corner" (the edge Left and Up reach), "low" and "high" (the two edges by value), "centre" (centre_of) and
    "short": a push of n presses that moved n presses' worth may have stopped short of the edge. "odd": records that
    moved with neither key, or a horizontal one that moved with Down alone."""
    g = edge_groups(regs)
    out = {}
    for axis, (s0, s1), (f0, f1), (far0, far1) in (("h", ("snap-h", "step-h"), ("low", "snap-h"), ("step-h", "step-v")),
                                                   ("v", ("step-h", "step-v"), ("snap-h", "step-h"), ("step-v", "high"))):
        a = out[axis] = {"keys": g[axis], "step": {}, "first": {}, "corner": {}, "low": {}, "high": {}, "centre": {},
                         "short": []}
        for k in g[axis]:
            s = regs[s1][k] - regs[s0][k]
            a["step"][k], a["first"][k], a["corner"][k] = s, regs[f1][k] - regs[f0][k], regs["low"][k]
            a["low"][k], a["high"][k] = sorted((regs["low"][k], regs["high"][k]))
            a["centre"][k] = centre_of(a["low"][k], a["high"][k])
            for what, moved in (("the low corner", regs["low"][k] - regs["base"][k]),
                                ("the far corner", regs[far1][k] - regs[far0][k])):
                if s and abs(moved) >= n * abs(s):
                    a["short"].append(f"{k}: the push of {n} presses toward {what} moved {n} presses' worth and may "
                                      "have stopped short of the edge: give --edge-presses more")
    moved = [k for k in regs["base"] if any(regs[t].get(k) != regs["base"].get(k) for t in EDGE_TAGS)]
    out["odd"] = [k for k in moved if k not in g["h"] and k not in g["v"]] + \
        [k for k in g["h"] if regs["high"].get(k) != regs["step-v"].get(k)]
    return out


def axis_way(cur: int, base: int, s: int, centre: int | None = None, low: int | None = None,
             high: int | None = None) -> list | None:
    """[[direction, presses]] that bring one record from `cur` to `base` under AF Frame Move Amt Standard, the direction
    +1 where the presses raise it; None where no press reaches `base`. `s`: Standard's step (no sign). What the
    registrations show of Standard (kit2_a1fin_framepos_edges_level and the grip runs, 2026-11-16): a press moves a whole
    step, the first off an edge too, and stops at an edge; a press that would cross the centre between the edges stops on
    it (every way back from the far corner landed on a start at the centre where whole steps would have passed it by up
    to a step). So: whole steps where the way does not cross the centre; to the centre itself, or to an edge, as many
    presses as reach it; across the centre, to it and on in whole steps from it; a start off this record's grid from
    `cur` but on the centre's, by the centre and back. Under Large no press stopped at the centre: not for Large."""
    import math
    if cur == base:
        return []
    d = 1 if base > cur else -1

    def straight(a, b):
        if abs(b - a) % s == 0:
            return abs(b - a) // s
        return math.ceil(abs(b - a) / s) if b in (low, high, centre) else None
    if centre is None or not min(cur, base) < centre < max(cur, base):
        k = straight(cur, base)
        if k is not None:
            return [[d, k]]
        if centre is None or cur == centre or (base - centre) % s:
            return None
        toward = 1 if centre > cur else -1
        return [[toward, math.ceil(abs(centre - cur) / s)], [-toward, abs(base - centre) // s]]
    rest = straight(centre, base)
    return None if rest is None else [[d, math.ceil(abs(centre - cur) / s) + rest]]


def edge_way_back(cur: dict, base: dict, m: dict) -> tuple:
    """([[key, presses]], {}) that bring a frame from `cur` to `base` (registrations' values) under Standard, the
    horizontal keys first, each axis by its first record that moves (`m`: edge_measure's, or standard_m's for a Large
    run), axis_way's way turned into the keys whose press moves that record so. ([], {key: how far the frame is from
    its start}) where no press reaches the start (set by touch, say, or under Large): nothing is guessed."""
    presses, off = [], {}
    for axis, plus, minus in (("h", "ms_right", "ms_left"), ("v", "ms_down", "ms_up")):
        keys = [k for k in m[axis]["keys"] if m[axis]["step"][k] or m[axis]["first"][k]]
        if not keys or cur.get(keys[0]) == base.get(keys[0]):
            continue
        k = keys[0]
        step = m[axis]["step"][k] or m[axis]["first"][k]
        way = axis_way(cur[k], base[k], abs(step), m[axis].get("centre", {}).get(k), m[axis]["low"].get(k),
                       m[axis]["high"].get(k))
        if way is None:
            off[k] = cur[k] - base[k]
            continue
        presses += [[plus if d * step > 0 else minus, n] for d, n in way if n]
    return ([], off) if off else (presses, {})


def standard_step(label: str, table=None) -> tuple | None:
    """(x, y): AF Frame Move Amt Standard's step for an area, from the hand tables' FRAME_STEPS of the camera the kit
    works on (`table` in its place), its label as the plan has it ("Spot: XL" is the table's "Spot XL"); None where the
    table has none."""
    for (option, area), xy in (FRAME_STEPS if table is None else table).items():
        if option == "Standard" and bare(area) == bare(label):
            return tuple(xy)
    return None


def standard_m(records: list, xy: tuple) -> dict | None:
    """An edge measure for the way back under Standard, from records as edge_records gives them (an edges line's
    "edges" too, a Large run's among them): each record's group, edges and centre as measured, its step Standard's from
    `xy` (FRAME_STEPS' x for a record whose name says X, y for Y), signed as the measured step raised it; None where a
    record's name gives no axis or its step had no sense."""
    out = {axis: {"keys": [], "step": {}, "first": {}, "corner": {}, "low": {}, "high": {}, "centre": {}, "short": []}
           for axis in ("h", "v")}
    out["odd"] = []
    for r in records:
        axis, plus = ("h", "Right") if r["keys"] == "Left/Right" else ("v", "Down")
        ax = axis_of(r.get("name"))
        if ax is None or not r.get("raises"):
            return None
        s = xy[0] if ax == "X" else xy[1]
        a, k = out[axis], r["key"]
        a["keys"].append(k)
        a["step"][k] = a["first"][k] = s if r["raises"] == plus else -s
        a["low"][k], a["high"][k], a["corner"][k] = r["low"], r["high"], r.get("corner")
        a["centre"][k] = centre_of(r["low"], r["high"])
    return out


def edge_records(m: dict, index: dict) -> list:
    """Each measured record for the edges file and the summary: {"key", "name" (the definition's), "keys" (the keys that
    move it), "low", "high", "corner", "step" (a press), "raises" (the key whose press raises it), "first" (the first
    press off the corner), "short"}; camera facts, never the start."""
    out = []
    for axis, keys, plus, minus in (("h", "Left/Right", "Right", "Left"), ("v", "Up/Down", "Down", "Up")):
        a = m[axis]
        for k in a["keys"]:
            out.append({"key": k, "name": (index.get(def_key(k)) or {}).get("name"), "keys": keys, "low": a["low"][k],
                        "high": a["high"][k], "corner": a["corner"][k], "step": abs(a["step"][k]),
                        "raises": plus if a["step"][k] > 0 else minus if a["step"][k] else None,
                        "first": abs(a["first"][k]), "short": [x for x in a["short"] if x.startswith(f"{k}:")]})
    return out


def edge_summary_of(line: dict) -> list:
    """An edges line in the summary: each record's edges, step and first press off the corner by key and name, whether
    the frame went back where it began (the difference by key where it did not), never the start nor the presses. Keys
    of the memory set the run registered (the line's "memory_set", slot 1's set 1 unless it says) by the definition's."""
    head = f"{line['area']} (code {line.get('code')}" + (f"; {line['context']})" if line.get("context") else ")")
    n = line.get("memory_set", 1)
    out = [f"{head}: edges, {line.get('edge_presses')} presses a push, {len(line.get('files') or {})} registrations"
           if line.get("edges") else f"{head}: edges not measured"]
    for r in line.get("edges") or []:
        raises = f" ({r['raises']} raises it)" if r["raises"] else ""
        out.append(f"    {r['keys']}  {shown_key(r['key'], n)}  {r['name'] or '(not in the definition)'}: {r['low']} to "
                   f"{r['high']}, a press {r['step']}{raises}, the first press off {r['corner']} moves {r['first']}"
                   + ("  [may have stopped short of an edge: give --edge-presses more]" if r["short"] else ""))
    if line.get("odd"):
        out.append(f"    moved with neither key, or with the other: {', '.join(shown_key(k, n) for k in line['odd'])}")
    if line.get("failed"):
        out.append(f"    failed: {line['failed']}")
    if line.get("stopped"):
        out.append(f"    stopped: {line['stopped']}")
    back = line.get("back")
    if back is None:
        out.append("    its frame was not moved" if not line.get("moved") else
                   f"    ITS FRAME MAY BE MOVED: on the shooting screen with {ROW} = {line['area']}, check its place by "
                   "hand" + (", or bring it back with --put-back RUN" if line.get("stopped") else ""))
    elif back["same"]:
        large = f"{AMT_ROW} Large" in (line.get("context") or "")
        out.append("    put back" + (" under Standard" if large else "")
                   + (" from the far corner after the failure" if "again-high" in (line.get("files") or {}) else "")
                   + ": the registration after it matched the first")
    else:
        off = "; ".join(f"{shown_key(x['key'], n)} {x['delta']:+d}" if isinstance(x.get("delta"), int)
                        else shown_key(x["key"], n) for x in back.get("off") or []) or "its place unknown"
        out.append(f"    NOT PUT BACK: {off} off: on the shooting screen with {ROW} = {line['area']}, move it back by "
                   "hand")
    return out


def edge_summary_lines(lines: list) -> list:
    """The edges summary, the last line of each area in each context, in the order they came."""
    last = {}
    for ln in lines:
        if ln.get("area"):
            last.pop((ln["area"], ln.get("context")), None)
            last[(ln["area"], ln.get("context"))] = ln
    return [s for ln in last.values() for s in edge_summary_of(ln)]


def edge_minutes(n: int, areas: int) -> tuple:
    """(minutes an area, minutes for `areas`) of an edge sweep: seven registrations, four presses read once they
    settle, four pushes of n presses and some sixty pushed back."""
    per = CHOOSE_S + len(EDGE_TAGS) * REG_S + REG_S + 4 * SETTLED_S + (4 * n + 60) * PUSHED_S
    return round(per / 60), round(per * areas / 60)


def off_of(changes: list) -> list:
    """[{"key", "delta"}] of a diff (changes_of), a record of several values by its key alone."""
    return [{"key": c["key"], **({} if isinstance(c["after"], list) or isinstance(c["before"], list)
                                 or c["before"] is None or c["after"] is None else {"delta": c["after"] - c["before"]})}
            for c in changes]


# ---------------------------------------------------------------- the slot screen (no camera)

def lit_slot(image) -> str | None:
    """The slot whose tab is lit on the Camera Set. Memory slot screen ("1", "2", "3", "M1"-"M4"), measured on the
    frame: one run of orange columns, a tab wide, in the top band, centred on a tab's place; None otherwise."""
    import numpy as np

    from camkit import screen
    band = screen._orange(image)[TAB_BAND[0]:TAB_BAND[1]] > 0.5
    xs = np.nonzero(band.mean(axis=0) > 0.5)[0]
    if not len(xs):
        return None
    width = int(xs[-1] - xs[0] + 1)
    if not 30 <= width <= 70 or width - len(xs) > 15:
        return None
    centre = (xs[0] + xs[-1]) / 2
    i = round((centre - TAB_FIRST) / TAB_PITCH)
    if not 0 <= i < len(SLOT_TABS) or abs(centre - (TAB_FIRST + i * TAB_PITCH)) > 15:
        return None
    return SLOT_TABS[i]


def memory_allowed(allow) -> bool:
    want = safety.clean_label(safety.fold(MEMORY_ROW))
    return any(safety.clean_label(safety.fold(x)) == want for x in allow or ())


# ---------------------------------------------------------------- the camera

def register_slot(cam, cycle, model, allow) -> dict:
    """Stills slot 1 registered: MENU, Camera Set. Memory by the scan, Enter (the row opened under --allow), the slot
    screen read as one and its lit tab measured as slot 1 (Left steps to it), Enter as drive.py's enter!:REGEX goes,
    "Registered." read. Returns {"frames", "said"}; the menu page is left open."""
    import drive
    from camkit.live import text_of
    from mode_switch import find, open_menu
    from prove_run import Failed
    open_menu(cam)
    find(cam, cycle, model, MEMORY_ROW)
    lit = drive.highlighted(cam.frame.image, cam.frame.path)
    if bare(MEMORY_ROW) not in bare(lit):
        raise Failed(f"the lit row reads {lit!r}, not {MEMORY_ROW} ({cam.frame.path.name})")
    row = cam.frame.path.name
    cam.press("enter")
    t = text_of(cam)
    if cam.read().kind == "notice":
        name = afreg_run.kept_notice(cam, f"Enter on {MEMORY_ROW}", t, "memory_notice")
        cam.press("menu")
        raise Failed(f"{MEMORY_ROW}: a notice instead of the slots ({name}; its words are in the run's events.jsonl)")
    if not SLOT_SCREEN.search(t):
        name = afreg_run.kept_notice(cam, f"Enter on {MEMORY_ROW}", t, "memory_screen")
        raise Failed(f"Enter on {MEMORY_ROW} opened {cam.read().kind}, not the slot screen ({name}; what it showed is "
                     "in the run's events.jsonl)")
    slot = lit_slot(cam.frame.image)
    for _ in range(len(SLOT_TABS)):
        if slot in (None, "1"):
            break
        cam.press("left")
        slot = lit_slot(cam.frame.image)
    if slot != "1":
        raise Failed(f"{MEMORY_ROW}: the lit tab measures as {slot or 'none'}, not slot 1 ({cam.frame.path.name})")
    t, lit = text_of(cam), drive.highlighted(cam.frame.image, cam.frame.path)
    # the slot screen reads as no known kind: the run's --allow is the consent to answer it, the shape check lifted and
    # the confirmation words still judged, here and by the camera (answer_once, 2026-11-14)
    consent = f"--allow {MEMORY_ROW!r}"
    why, _ = drive.press_decision(f"enter!:{SLOT_SCREEN.pattern}", "enter", lit, t, cam.read().kind, False, allow,
                                  consent=consent)
    if why:
        raise Failed(f"{MEMORY_ROW}: Enter refused on the slot screen ({cam.frame.path.name}): {why}")
    slots = cam.frame.path.name
    cam.answer_once = consent
    cam.press("enter")
    said = text_of(cam)
    if not re.search(r"registered", said, re.I):
        time.sleep(0.5)
        cam.refresh("registered")
        said = text_of(cam)
    m = re.search(r"registered[^.\n]*\.?", said, re.I)
    if not m:                               # the screen may be the slot screen, which lists the live settings
        name = afreg_run.kept_notice(cam, "Enter on slot 1", said, "memory_screen")
        raise Failed(f"{MEMORY_ROW}: no \"Registered.\" after Enter on slot 1 ({name}; what it showed is in the run's "
                     "events.jsonl)")
    notice = cam.frame.path.name
    time.sleep(1.0)                                     # the notice goes by itself; the menu page comes back
    cam.refresh("after-registered")
    return {"frames": [row, slots, notice, cam.frame.path.name], "said": m.group(0).strip()}


def download(cam, link, hdmi, tag: str) -> tuple:
    """The menu closed, the shooting screen, a download; (it, when it came)."""
    from prove_run import to_shooting
    from runner import close_screen
    close_screen(cam, link)
    to_shooting(link, hdmi, f"the download {tag}")
    time.sleep(1)
    return link.download(tag), time.monotonic()


def back_to_shooting(cam, wait_s: float = NOTICE_S) -> bool:
    end = time.monotonic() + wait_s
    while time.monotonic() < end:
        time.sleep(0.5)
        if cam.refresh("notice-wait").kind == "shooting":
            return True
    return False


def turned_check(grip: str | None, check: str) -> str:
    """What a failed check adds held vertically: that it cannot be made on the turned screen, so the run stops; ""
    level."""
    return (f"; held vertically (grip {grip}) {check} cannot be made on this turned screen, so the run stops here"
            if grip else "")


def press_moves(cam, moves: list, sent: list, done: list, grip: str | None = None, run=None) -> None:
    """The multi-selector's presses on the shooting screen, each named for it (on_shooting: the link sends no key but
    MENU there unnamed, decision 21) and each read, filling `sent` ({"key", "frame", "screen"}, and
    "refused" or "notice" when so) and `done` ([key, presses taken], one per move) as they go, so a caller whose area
    fails knows what was taken. A press the link refuses, or one a notice answers (waited out, NOTICE_S), is recorded
    and not counted; a screen that is not the shooting screen before a press, or a notice that stays, fails the area.
    With a grip the screen's kind is judged as level and a notice's words are read upright (afreg_run.shooting_words,
    `run`'s upright folder); a failure says the check cannot be made on the turned screen (turned_check)."""
    from camkit.link import LinkError
    from prove_run import Failed
    for key, n in moves:
        done.append([key, 0])
        for _ in range(n):
            if cam.read().kind != "shooting":
                raise Failed(f"not on the shooting screen before {WORDS[key]} ({cam.read().kind}, {cam.frame.path.name})"
                             + turned_check(grip, "the check that a press goes out on the shooting screen"))
            try:
                cam.press(key, on_shooting=key)     # named: the shooting screen is where this press moves the frame
            except (LinkError, safety.Refused) as e:
                sent.append({"key": key, "refused": f"{type(e).__name__}: {e}"[:200]})
                continue
            rec = {"key": key, "frame": cam.frame.path.name, "screen": cam.read().kind}
            sent.append(rec)
            if rec["screen"] == "shooting":
                done[-1][1] += 1
                continue
            rec["notice"] = " ".join(afreg_run.shooting_words(cam, run, grip).split())[:200]
            if not back_to_shooting(cam):
                cam.run.log("shooting_screen_left", step=WORDS[key], frame=rec["frame"], notice=rec["notice"])
                raise Failed(f"{WORDS[key]} left the shooting screen ({rec['screen']}, {rec['frame']}; what it showed is "
                             "in the run's events.jsonl)"
                             + turned_check(grip, "the check that the press left the camera on the shooting screen"))


def prepare(cam, link, hdmi, run, cycle, model, focus: bool, drive: bool, start: Path, amt: str | None = None,
            index: dict | None = None, grip: str | None = None, circ: bool = False, vh: bool = True) -> list:
    """The setup through the menu (setup_steps, each as afreg_run.prepare takes it; Switch V/H AF Area as the grip has
    it, none where vh is False: Movie and S&Q offer no such row), then a download kept in setup.jsonl with the keys it
    changed; returns the steps. The count only is printed.
    With amt, the download must hold the code the definition (`index`, its settings by key) gives that option in AF
    Frame Move Amt's record (amt_code), and with circ (--edges) Circ. of Focus Point's Does Not Circulate's
    (setting_code): a menu that did not take either fails the run before any area, the value found never said (the
    restore puts the setup back)."""
    from camkit import camset
    from mode_switch import open_menu
    from prove_run import LOCK_S, Failed, held_value, to_shooting
    from runner import close_screen
    want = amt_code(index or {}, amt) if amt else None
    if amt and want is None:
        raise Failed(f"the definition gives no code for {AMT_ROW} = {amt}: the run could not tell whether the camera "
                     "took it")
    stops = setting_code(index or {}, [CIRC_ROW], CIRC_OFF) if circ else None
    if circ and stops is None:
        raise Failed(f"the definition gives no code for {CIRC_ROW} = {CIRC_OFF}: the run could not tell whether the "
                     "camera took it")
    rows = setup_rows(amt, grip, circ)
    steps = []
    for kind, what in setup_steps(focus, drive, amt, grip, circ, vh):
        open_menu(cam)
        if kind == "dial":
            afreg_run.focus_dial_by_menu(cam, cycle, model, what)
        elif kind == "drive":
            afreg_run.drive_single(cam, cycle, model)
        else:
            path, option = rows[what]
            afreg_run.set_setup_row(cam, cycle, model, path, option)
        close_screen(cam, link)
        time.sleep(1.0)
        steps.append(afreg_run.step_name(kind, what))
    to_shooting(link, hdmi, "the download after the setup")
    time.sleep(1)
    ref = link.download("after-setup")
    after = camset.read(ref)
    changed = [c.key for c in camset.diff(camset.read(start), after)]
    took = held_value(after, want[0]) == want[1] if want else None
    stopped = held_value(after, stops[0]) == stops[1] if stops else None
    jsonl.append(run.dir / "setup.jsonl", {"t": round(time.time(), 3), "steps": steps, "start": start.name,
                                           "after": ref.name, "changed": changed,
                                           **({"frame_move_amt": {"asked": amt, "took": took}} if amt else {}),
                                           **({"circ_of_focus_point": {"asked": CIRC_OFF, "took": stopped}}
                                              if circ else {})})
    print(f"setup: {'; '.join(steps)}; {len(changed)} records now differ from the start file (the restore puts them "
          "back)", flush=True)
    if amt and not took:
        raise Failed(f"{AMT_ROW} did not take {amt} through the menu; the setup is undone by the restore")
    if circ and not stopped:
        raise Failed(f"{CIRC_ROW} did not take {CIRC_OFF} through the menu: a frame could wrap round at an edge; the "
                     "setup is undone by the restore")
    time.sleep(LOCK_S)
    return steps


def one_area(cam, link, hdmi, run, cycle, model, labels, axes, t: dict, r: tuple, a, index: dict, owed: list) -> dict:
    """One area: chosen, slot 1 registered, a download; the frame moved, registered, a download; the diff; the frame put
    back (and, with --check-back, registered and downloaded once more). `owed` holds the presses that would put the
    frame back while it is moved, for the caller to send if the area fails. Held vertically (a.grip down or up) the
    dialog and the shooting screen are read as afreg_run reads them turned, unless Vertical Display is Off in the start
    download (a.vertical, which areas sets: every screen level); --grip level reads them as level. With any grip the line
    judges no direction. Returns the area's line."""
    from camkit import camset
    from prove_run import to_shooting
    from runner import changes_of
    grip = getattr(a, "grip", None)
    turned = turned_of(grip, getattr(a, "vertical", None))
    got = afreg_run.choose_area(cam, run, cycle, model, labels, axes, r, turned)
    to_shooting(link, hdmi, "the shooting screen with the area chosen")
    frames = {"chosen": got["chosen_frame"], "after_ok": got["row_frame"]}
    frames["base_registration"] = register_slot(cam, cycle, model, a.allow)["frames"]
    base, at = download(cam, link, hdmi, f"base-{slug(t['label'])}")
    afreg_run.ready_to_hold(cam, at, run, turned)       # the download's message gone, the menu lock passed
    sent, done = [], []
    try:
        press_moves(cam, t["moves"], sent, done, turned, run)
    finally:
        owed[:] = back_of(done)
    frames["moves"] = [x["frame"] for x in sent if x.get("frame")]
    frames["moved_registration"] = register_slot(cam, cycle, model, a.allow)["frames"]
    moved, at = download(cam, link, hdmi, f"moved-{slug(t['label'])}")
    changes = changes_of(camset.diff(camset.read(base), camset.read(moved)))
    afreg_run.ready_to_hold(cam, at, run, turned)
    back, back_sent, back_done = list(owed), [], []
    try:
        press_moves(cam, back, back_sent, back_done, turned, run)
    finally:
        owed[:] = left_to_send(back, back_done)
    frames["put_back"] = [x["frame"] for x in back_sent if x.get("frame")]
    files = {"base": base.name, "moved": moved.name}
    back_changes = None
    if a.check_back:
        frames["back_registration"] = register_slot(cam, cycle, model, a.allow)["frames"]
        again, at = download(cam, link, hdmi, f"back-{slug(t['label'])}")
        files["back"] = again.name
        back_changes = changes_of(camset.diff(camset.read(base), camset.read(again)))
        afreg_run.ready_to_hold(cam, at, run, turned)   # the menu lock passed before the next area's MENU
    line = area_line(t, changes, index, sent + [dict(x, put_back=True) for x in back_sent], done, back_done, frames,
                     files, back_changes, grip, upright=bool(turned))
    if owed:
        line["put_back_short"] = list(owed)
    return line


def zone_sweep(cam, link, hdmi, run, cycle, model, labels, axes, t: dict, r: tuple, a, index: dict, owed: list,
               tag: dict) -> dict:
    """The nine places of the Zone grid: Zone chosen; slot 1 registered and a download at the start (its place read from
    the download); the frame led to the upper left corner by exact presses (corner_moves), then row by row
    (SWEEP_STEPS), slot 1 registered and a download "zone-<name>" at each, the place read from set1:0x019a and checked
    against the route; the frame put back where it started, slot 1 registered once more and a download "zone-back"
    which must match the start's. One line a place in zone_grid.jsonl, proof lines in proofs.jsonl. `owed`: the net
    presses that put the frame back at the start, kept current for the caller. Held vertically (a.grip down or up) the
    area is chosen and the screens read as the grip runs read them (turned unless Vertical Display is Off: a.vertical),
    and the proof lines cover that grip's records (sweep_records). A place that does not read as the route led ends the
    walk with what the keys did, the key mappings that explain it (zone_fits: the step's own move from a confirmed place;
    for the corner, the presses from the start, never said, the start being the owner's), and the frame is still put back
    and checked; a zone-back off its start is brought to it once by zone_back_presses under the one mapping the walk
    showed (the level one where every place confirmed) and checked again. Returns the sweep's summary line, "failed"
    where a place did not read as routed."""
    from camkit import camset
    from prove_run import held_value, to_shooting
    from runner import changes_of
    grip = getattr(a, "grip", None)
    turned = turned_of(grip, getattr(a, "vertical", None))
    got = afreg_run.choose_area(cam, run, cycle, model, labels, axes, r, turned)
    to_shooting(link, hdmi, "the shooting screen with Zone chosen")
    register_slot(cam, cycle, model, a.allow)
    start, at = download(cam, link, hdmi, "zone-start")
    afreg_run.ready_to_hold(cam, at, run, turned)
    cs0 = camset.read(start)
    code0 = held_value(cs0, ZONE_CURRENT)
    place0 = code_place(code0)
    if place0 is None:
        from prove_run import Failed
        raise Failed(f"the start download holds no zone place the table names ({ZONE_CURRENT}, {start.name})")
    # the start place is the owner's: read from the download and kept there, never printed (decision 16)
    print(f"  zone sweep: the start place was read from the download ({start.name})", flush=True)
    done, sent, rows, finding = [], [], [], None
    maps = list(KEY_MAPS)                   # the key mappings the walk has not ruled out

    def go(moves):
        try:
            press_moves(cam, moves, sent, done, turned, run)
        finally:
            owed[:] = net_back(done)

    def registered(tag_):
        register_slot(cam, cycle, model, a.allow)
        dat, at_ = download(cam, link, hdmi, tag_)
        afreg_run.ready_to_hold(cam, at_, run, turned)
        return dat, camset.read(dat)
    corner = corner_moves(place0)
    go(corner)
    prev_cs, prev_name, prev_place = cs0, start.name, place0
    for k, (step, expected) in enumerate(sweep_route()):
        if step:
            go([[step, 1]])
        want = place_name(expected)
        dat, cs = registered(f"zone-{slug(want)}")
        code = held_value(cs, ZONE_CURRENT)
        changes = changes_of(camset.diff(prev_cs, cs))
        line = sweep_line(k, expected, code, changes, dat.name, index)
        presses = [[step, 1]] if step else corner
        read = code_place(code)
        fits = [] if read is None else zone_fits(prev_place, presses, read)
        maps = [m for m in maps if m in fits]
        line.update(step=WORDS[step] if step else "to the upper left", fits=[mapping_words(m) for m in maps])
        held = {rec: held_value(cs, rec.replace("set:", "set1:", 1)) for rec in sweep_records(index, grip)}
        place_written(run.dir, line, held, prev_name, changes, index, tag, grip)     # proof lines once confirmed only
        rows.append(line)
        if not line["confirmed"]:
            # what an unconfirmed place's download holds may tell the start place, the owner's: in zone_grid.jsonl only;
            # what a single step from a confirmed place did is the keys' own doing, and is said
            if step and read is not None:       # from a place that read as routed: the key's own move
                level = key_vector(step, KEY_MAPS[0])
                did = (f"{WORDS[step]} moved the zone {read[0] - prev_place[0]:+d} column(s), "
                       f"{read[1] - prev_place[1]:+d} row(s), where level it moves {level[0]:+d} column(s), "
                       f"{level[1]:+d} row(s)")
            else:
                did = "the presses toward the upper left led elsewhere"
            explained = (f"; the keys act turned: {mapping_words(maps[0])}" if len(maps) == 1 else
                         "; no turn or mirror of the level keys explains it (the zone may wrap at an edge)" if not maps
                         else f"; {len(maps)} turns or mirrors of the keys explain it")
            finding = f"place {k + 1} ({want}) does not read as routed: {did}{explained}"
            print(f"  zone sweep {k + 1}/9: {want} NOT as routed: {did}{explained} (what the download holds is in "
                  "zone_grid.jsonl)", flush=True)
            break
        print(f"  zone sweep {k + 1}/9: {want} -> code {code} ({line['name']}), confirmed; records: "
              + ("; ".join(f"{g} {', '.join(keys)}" for g, keys in line["groups"].items() if keys) or "none"),
              flush=True)
        prev_cs, prev_name, prev_place = cs, dat.name, read
    back = net_back(done)
    go(back)
    again, cs_back = registered("zone-back")
    off = changes_of(camset.diff(cs0, cs_back))
    now = code_place(held_value(cs_back, ZONE_CURRENT))
    fixed = []
    mapping = KEY_MAPS[0] if finding is None else maps[0] if len(maps) == 1 else None
    if off and now is not None and now != place0 and mapping is not None:
        # counted presses put back nothing where a press met an edge: once more, straight, under the keys' mapping
        fixed = zone_back_presses(now, place0, mapping)
        go(fixed)
        again, cs_back = registered("zone-back2")
        off = changes_of(camset.diff(cs0, cs_back))
    # the presses that put it back tell where it started: in the sweep's line only, never printed
    print("  zone sweep: the registration after the put-back "
          + ("matched the start's" if not off else
             f"differs from the start's in {', '.join(c['key'] for c in off)}: on the shooting screen with {ROW} = Zone, "
             f"move it back by hand to where it began (the place {start.name} holds)"), flush=True)
    return {"t": round(time.time(), 3), "sweep": "zone-grid", "places": len(rows),
            "confirmed": sum(x["confirmed"] for x in rows), "put_back": back + fixed, "back_same": not off,
            "back_off": [c["key"] for c in off], "files": {"start": start.name, "back": again.name},
            "frames": {"chosen": got["chosen_frame"]}, **({"failed": finding} if finding else {}), **tag}


def push(cam, moves: list, turned: str | None = None, gap: float = PUSH_GAP) -> list:
    """The multi-selector's presses on the shooting screen sent quickly, for an edge or the way back: before each, a
    fresh frame read (LiveCamera.reading: the playback view is no shooting screen), and the press sent straight through
    the link, named for the shooting screen and judged there on that screen (Link.press, decision 21), `gap` s apart,
    none waited on to settle: a press that meets an edge moves nothing, and where the frame went is read from the next
    registration. A screen not read as the shooting screen stops the push before its press (Failed), a guard's refusal
    too; a press the camera refused is a press lost, which the next registration shows. Returns [[key, presses sent]]."""
    from camkit.link import LinkError
    from prove_run import Failed
    sent = []
    for key, n in moves:
        sent.append([key, 0])
        for _ in range(n):
            s = cam.reading(cam.hdmi.grab(save=False))
            if s.kind != "shooting":
                cam.refresh("push-stopped")
                raise Failed(f"not on the shooting screen before {WORDS[key]} ({s.kind}, {cam.frame.path.name})"
                             + turned_check(turned, "the check that a press goes out on the shooting screen"))
            try:
                cam.link.press(key, on_shooting=frozenset({key}), screen=s)
            except safety.Refused as e:
                cam.refresh("push-refused")
                raise Failed(f"{WORDS[key]} refused by the kit's guards ({e})") from None
            except LinkError:
                continue
            sent[-1][1] += 1
            time.sleep(gap)
    cam.refresh("pushed")
    return sent


class Walk:
    """One area's registrations and presses for --edges and --put-back: each registration of slot 1 downloaded and kept
    by its tag (reg: "files", "frames", the settings file read), the pushes (push) and the single presses read once they
    settle (press_moves), AF Frame Move Amt set through its menu row (set_amt), and the way back to a start, checked
    (way_back). `line` is the area's line as it grows; `amt` {"now": the option the camera is on} is the run's, shared
    by its areas."""

    def __init__(self, cam, link, hdmi, run, cycle, model, a, turned, t: dict, prefix: str, amt: dict | None = None):
        self.cam, self.link, self.hdmi, self.run, self.cycle, self.model, self.a = cam, link, hdmi, run, cycle, model, a
        self.turned, self.t, self.prefix, self.amt = turned, t, prefix, amt if amt is not None else {"now": None}
        self.cs, self.files, self.frames = {}, {}, {}
        self.line = {"t": round(time.time(), 3), "area": t["label"], "code": t["code"], "files": self.files,
                     "frames": self.frames, "moved": False}

    def reg(self, tag: str):
        from camkit import camset
        self.frames[tag] = register_slot(self.cam, self.cycle, self.model, self.a.allow)["frames"]
        path, at = download(self.cam, self.link, self.hdmi, f"{self.prefix}-{tag}-{slug(self.t['label'])}")
        self.files[tag] = path.name
        afreg_run.ready_to_hold(self.cam, at, self.run, self.turned)
        self.cs[tag] = camset.read(path)

    def held(self, tag: str, keys) -> dict:
        from prove_run import held_value
        return {k: held_value(self.cs[tag], k) for k in keys}

    def pushed(self, moves: list):
        self.line["moved"] = True
        self.frames.setdefault("pushes", []).append(push(self.cam, moves, self.turned))

    def single(self, moves: list):
        from prove_run import Failed
        self.line["moved"] = True
        sent, done = [], []
        press_moves(self.cam, moves, sent, done, self.turned, self.run)
        if done != [list(x) for x in moves]:
            raise Failed(f"{say_moves(moves)} off the edge went out as {say_moves(done)}: the step cannot be read")

    def values(self, tags: list, names: list | None = None) -> dict:
        """{tag: {key: value}} of every scalar record two of `tags` in a row differ in (`names`: the tags they stand
        for in edge_measure)."""
        from camkit import camset
        keys = []
        for x, y in zip(tags, tags[1:], strict=False):
            keys += [c.key for c in camset.diff(self.cs[x], self.cs[y]) if c.key not in keys
                     and not isinstance(c.before, list) and not isinstance(c.after, list)]
        return {(names or tags)[i]: self.held(tag, keys) for i, tag in enumerate(tags)}

    def set_amt(self, option: str):
        """AF Frame Move Amt put on `option` through its menu row, as the setup puts it, and the shooting screen back."""
        from mode_switch import open_menu
        from prove_run import to_shooting
        from runner import close_screen
        open_menu(self.cam)
        afreg_run.set_setup_row(self.cam, self.cycle, self.model, [AMT_ROW], option)
        close_screen(self.cam, self.link)
        to_shooting(self.link, self.hdmi, f"the shooting screen with {AMT_ROW} = {option}")
        self.amt["now"] = option

    def way_back(self, cur: dict, base: dict, m: dict, check, keys):
        """From `cur` to `base` (values by key) by edge_way_back's presses on m's steps (Standard's), each landing
        registered and judged by check(tag) ([{"key", "delta"}] still off, [] when back); a landing still off planned
        again from there, EDGE_TRIES times at most; a start no press reaches said, nothing more pressed. Sets the line's
        "back" ({"same", "off", "tries", "presses", "under": "Standard"}) and, short of it, "failed"."""
        tries, presses_all = 0, []
        presses, off = edge_way_back(cur, base, m)
        while not off:
            if presses:
                self.pushed(presses)
                presses_all.append(presses)
            tries += 1
            tag = f"back{sum(1 for x in self.files if x.startswith('back')) + 1}"     # numbered across the area
            self.reg(tag)
            left = check(tag)
            self.line["back"] = {"same": not left, "off": left, "tries": tries, "presses": presses_all,
                                 "under": "Standard"}
            if not left or tries > EDGE_TRIES:
                break
            cur = self.held(tag, keys)
            presses, off = edge_way_back(cur, base, m)
            if not presses and not off:
                break                               # the measured records are back; the others are said in "off"
        if off:
            self.line["back"] = {"same": False, "off": [{"key": k, "delta": cur[k] - base[k]} for k in keys
                                                        if cur.get(k) != base.get(k)],
                                 "unreachable": sorted(off), "tries": tries, "presses": presses_all, "under": "Standard"}
        if not self.line["back"]["same"]:
            self.line["failed"] = (f"the frame is not where it began after {tries} registration"
                                   f"{'s' if tries != 1 else ''} on the way back"
                                   + (": no press reaches its start" if off else ""))


def amt_keys(index: dict, n: int = 1) -> set:
    """AF Frame Move Amt's live record and its copy in memory set `n` (the slot registered: a registration writes it):
    a run that sets the row leaves them out of its checks that a frame is back."""
    got = amt_code(index, "Standard") or amt_code(index, "Large")
    return {got[0], got[0].replace("global:", f"set{n}:", 1)} if got else set()


def edge_area(cam, link, hdmi, run, cycle, model, labels, axes, t: dict, r: tuple, a, index: dict,
              turned: str | None = None, amt: str | None = "Standard", amt_state: dict | None = None,
              held: dict | None = None) -> dict:
    """One area's edges (--edges), measured under AF Frame Move Amt `amt`: chosen; slot 1 registered at its start
    (base); pushed a.edge_presses Left and Up to the low corner (low); Right 1 (snap-h: what Right moves), Right 1 and
    Down 1 (step-h: Right's step, what Down moves), Down 1 and Right pushed (step-v: Down's step, the far horizontal
    edge), Down pushed (high: the far corner), each registered and downloaded: edge_measure. The single presses are read
    once they settle (press_moves), the pushes sent quickly (push). Then the way back under Standard, the one it is
    proved under (axis_way): a Large run sets Standard through its row first and counts in Standard's step
    (standard_step, standard_m), and sets Large again before its next area's start, which must read Large. The way back
    is registered and checked against the start's registration record by record (AF Frame Move Amt's own records left
    out); a press the camera lost is made good and checked again, EDGE_TRIES times at most; a start no press reaches is
    said, nothing more pressed. A failure once the frame has moved closes the screen, measures again on the low side what
    is not yet known, pushes the frame to the far corner and brings it back from there under Standard as above. Returns
    the area's line, which says whether the frame is back ("back") or may be elsewhere ("moved" with no "back"). A STOP
    (camkit.link.StopRequested), or anything else that is not the area's own failure, here or in the recovery, goes up
    to the caller with nothing more pressed: `held` keeps the area's Walk ("walk") from the start, so edge_loop writes
    its line all the same (stopped_line)."""
    from camkit import camset
    from prove_run import Failed, held_value, to_shooting
    from runner import changes_of, close_screen
    n, large = a.edge_presses, amt == "Large"
    amt_state = amt_state if amt_state is not None else {"now": amt}
    w = Walk(cam, link, hdmi, run, cycle, model, a, turned, t, "edge", amt_state)
    w.line["edge_presses"] = n
    if held is not None:
        held["walk"] = w
    skip = amt_keys(index, getattr(a, "memory_set", None) or 1)
    xy = standard_step(t["label"]) if large else None

    def check(tag):
        return off_of([c for c in changes_of(camset.diff(w.cs["base"], w.cs[tag])) if c["key"] not in skip])

    def back_m(regs, m):
        """The way back's measure: the run's own (Standard), or Standard's step on a Large run's groups and edges."""
        if not large:
            return m
        got = standard_m(edge_records(m, index), xy) if xy else None
        if got is None:
            raise Failed(f"no Standard step for {t['label']} (the hand tables' FRAME_STEPS, the records' X and Y): the "
                         "way back cannot be counted")
        return got

    def to_standard():
        if large and w.amt["now"] != "Standard":
            w.set_amt("Standard")

    try:
        if large and w.amt["now"] != "Large":
            w.set_amt("Large")
        got = afreg_run.choose_area(cam, run, cycle, model, labels, axes, r, turned)
        w.frames.update(chosen=got["chosen_frame"], after_ok=got["row_frame"])
        to_shooting(link, hdmi, "the shooting screen with the area chosen")
        w.reg("base")
        want = amt_code(index, amt) if amt else None
        if want and held_value(w.cs["base"], want[0]) != want[1]:
            raise Failed(f"the start's registration does not hold {AMT_ROW} {amt}'s code in {want[0]}: nothing was "
                         "measured")
        w.pushed([["ms_left", n], ["ms_up", n]])
        w.reg("low")
        w.single([["ms_right", 1]])
        w.reg("snap-h")
        w.single([["ms_right", 1], ["ms_down", 1]])
        w.reg("step-h")
        w.single([["ms_down", 1]])
        w.pushed([["ms_right", n]])
        w.reg("step-v")
        w.pushed([["ms_down", n]])
        w.reg("high")
        regs = w.values(list(EDGE_TAGS))
        m = edge_measure(regs, n)
        w.line.update(values=regs, odd=m["odd"], edges=edge_records(m, index))
        mb = back_m(regs, m)
        to_standard()
        w.way_back(regs["high"], regs["base"], mb, check, list(regs["base"]))
    except Failed as e:
        w.line["failed"] = str(e)
        close_screen(cam, link)
        if w.line["moved"] and not (w.line.get("back") or {}).get("same"):
            w.line.pop("back", None)
            try:
                to_shooting(link, hdmi, "the shooting screen to bring the frame back")
                low = ["low", "snap-h", "step-h", "step-v"]
                if not all(x in w.cs for x in low):
                    w.pushed([["ms_left", n], ["ms_up", n]])
                    w.reg("again-low")
                    w.single([["ms_right", 1]])
                    w.reg("again-snap-h")
                    w.single([["ms_right", 1], ["ms_down", 1]])
                    w.reg("again-step-h")
                    w.single([["ms_down", 1]])
                    w.reg("again-step-v")
                    low = [f"again-{x}" for x in low]
                to_standard()
                w.pushed([["ms_right", n], ["ms_down", n]])
                w.reg("again-high")
                regs = w.values(["base", *low, "again-high"], list(EDGE_TAGS))
                m = edge_measure(regs, n)
                w.way_back(regs["high"], regs["base"], back_m(regs, m), check, list(regs["base"]))
                w.line["failed"] = str(e)           # the area's own failure, the frame brought back or not
            except Failed as e2:
                w.line["recovery_failed"] = str(e2)
                close_screen(cam, link)
    return w.line


def stopped_line(w, e) -> dict | None:
    """The line of an area a STOP (or anything that is not its own failure) ended, `w` its Walk: None where its frame
    never moved (nothing to bring back); else its line as far as it went, "moved", no "back", "stopped" (what ended
    it) and "values" (each registration's place records, those that changed between them: the start among them) where
    two registrations or more were made. Nothing is pressed here."""
    if w is None or not w.line.get("moved"):
        return None
    w.line["stopped"] = f"{type(e).__name__}: {e}"[:300]
    if len(w.cs) > 1 and "values" not in w.line:
        with contextlib.suppress(Exception):    # a download that cannot be read: its files still name it
            w.line["values"] = w.values(list(w.cs))
    return w.line


def edge_loop(s, a, run, hdmi, cycle, model, labels, axes, todo, routes, index, tag, lines, setup, turned, amt=None):
    """--edges's session body after the setup: each area of the plan (edge_area), its line written to edges.jsonl and
    summed up as it comes. An area whose frame is not known to be back ends the run; a failed area whose frame never
    moved, or came back, ends it as an area does in a framepos run (held vertically at once, else three in a row).
    edges_summary.txt is written again after each area. AF Frame Move Amt is the setup's `amt` at the start, followed
    from area to area (a Large run's way back is made under Standard). An area a STOP, or anything else that is not its
    own failure, ends once its frame has moved has its line written all the same (stopped_line: moved, no "back", its
    registrations so far), nothing more pressed, so --put-back finds the frame."""
    from runner import write_text
    grip = getattr(a, "grip", None)
    in_a_row, amt_state = 0, {"now": amt}
    for t in todo:
        held = {}
        try:
            line = edge_area(s.cam, s.link, hdmi, run, cycle, model, labels, axes, t, routes[t["label"]], a, index,
                             turned, amt, amt_state, held)
        except BaseException as e:
            line = stopped_line(held.get("walk"), e)
            if line is not None:
                line.update(tag, setup=setup)
                jsonl.append(run.dir / "edges.jsonl", line)
                lines.append(line)
                write_text(run.dir / "edges_summary.txt",
                           "\n".join(edge_summary_lines(jsonl.read(run.dir / "edges.jsonl"))) + "\n")
                print("\n".join(edge_summary_of(line)), flush=True)
            print(f"  {t['label']}: stopped with its frame perhaps moved: on the shooting screen with {ROW} = "
                  f"{t['label']}, check its place by hand, or bring it back with --put-back {run.dir.name}", flush=True)
            raise
        line.update(tag, setup=setup)
        jsonl.append(run.dir / "edges.jsonl", line)
        lines.append(line)
        print("\n".join(edge_summary_of(line)), flush=True)
        write_text(run.dir / "edges_summary.txt",
                   "\n".join(edge_summary_lines(jsonl.read(run.dir / "edges.jsonl"))) + "\n")
        if line["moved"] and not (line.get("back") or {}).get("same"):
            print(f"the frame of {t['label']} is not known to be where it began: stopping; --put-back {run.dir.name} "
                  "brings it back where a press reaches its start", flush=True)
            break
        in_a_row = in_a_row + 1 if line.get("failed") else 0
        if line.get("failed") and grip in TURNED:
            print(f"held vertically (grip {grip}), a failed area ends the run: stopping", flush=True)
            break
        if in_a_row == 3:
            print("three areas in a row failed: stopping", flush=True)
            break


# ---------------------------------------------------------------- --put-back: a frame an edges run left behind

def left_behind(lines: list) -> list:
    """The lines of an edges run whose frame moved and is not back, the last line of each area in each context."""
    last = {}
    for ln in lines:
        if ln.get("area"):
            last.pop((ln["area"], ln.get("context")), None)
            last[(ln["area"], ln.get("context"))] = ln
    return [ln for ln in last.values() if ln.get("moved") and not (ln.get("back") or {}).get("same")]


def put_back_plan(line: dict, table=None, index: dict | None = None) -> tuple:
    """(Standard's measure for the way back, why not): what --put-back needs of an edges line to bring its frame back:
    the start's registration of the measured records ("values" "base", "edges") and Standard's step for its area
    (standard_step, standard_m). The way back's presses are counted from the far corner once it is registered. A line
    with no edges (an area stopped before they were measured: stopped_line, files_lines) is planned from its
    registrations alone (files_m, by the definition `index`'s names)."""
    stopped = not line.get("edges") and (line.get("stopped") or line.get("from_files"))
    if stopped:
        if len(line.get("values") or {}) < 2 or not line["values"].get("base"):
            return None, ("no registration was made after its start, so which records hold its place is not known "
                          f"(its start: {(line.get('files') or {}).get('base')})")
    elif not line.get("edges") or not (line.get("values") or {}).get("base"):
        return None, "the run measured no edges for it, so which records hold its place is not known"
    xy = standard_step(line["area"], table)
    if xy is None:
        return None, f"the hand tables' FRAME_STEPS give no Standard step for {line['area']}"
    if stopped:
        return files_m(line, xy, index or {})
    m = standard_m(line["edges"], xy)
    if m is None:
        return None, "a measured record's name gives no X or Y, so Standard's step cannot be put on it"
    far = (line["values"].get("high") or {})
    _, off = edge_way_back(far, line["values"]["base"], m) if far else ({}, {})
    if off:
        return None, ("no press reaches its start from the far corner ("
                      + "; ".join(f"{shown_key(k, line.get('memory_set', 1))} {d:+d}" for k, d in off.items()) + ")")
    return m, ""


def files_m(line: dict, xy: tuple, index: dict) -> tuple:
    """(Standard's measure for the way back, why not) of an area stopped before its edges were measured, from its
    registrations alone: its place records are those that changed between them (the line's "values": the start and the
    low corner, say), each record's axis its definition name's X or Y (`index`), its step Standard's (`xy`, FRAME_STEPS),
    Right raising X and Down raising Y as the camera level moves them (held vertically the keys may turn, and nothing
    measured says how: refused), its centre the grid's (GRID_CENTRE: where every frame's edges lie either side alike,
    at any Aspect Ratio), its low edge the low corner's registration where there is one ("low", the push having reached
    it) and its high edge that mirrored over the centre."""
    if line.get("grip") not in (None, "level"):
        return None, (f"held {held_words(line['grip'])} the keys may move the frame otherwise than level, and the run "
                      "measured nothing that says how: move it back by hand")
    vals = line["values"]
    base, low = vals["base"], vals.get("low") or {}
    out = {axis: {"keys": [], "step": {}, "first": {}, "corner": {}, "low": {}, "high": {}, "centre": {}, "short": []}
           for axis in ("h", "v")}
    out["odd"] = []
    for k in base:
        ax = axis_of((index.get(def_key(k)) or {}).get("name"))
        if ax is None:
            return None, f"{shown_key(k)}'s name in the definition gives no X or Y, so Standard's step cannot be put on it"
        a, c = out["h" if ax == "X" else "v"], GRID_CENTRE[ax]
        a["keys"].append(k)
        a["step"][k] = a["first"][k] = xy[0] if ax == "X" else xy[1]
        a["centre"][k], a["corner"][k] = c, low.get(k)
        a["low"][k], a["high"][k] = (low[k], 2 * c - low[k]) if low.get(k) is not None else (None, None)
    if not out["h"]["keys"] and not out["v"]["keys"]:
        return None, "no record changed between its registrations, so which records hold its place is not known"
    return out, ""


EDGE_FILE = re.compile(r"^(\d+)_edge-(.+)\.DAT$")
EDGE_TAG = re.compile(r"^(?:again-)?(?:base|low|snap-h|step-h|step-v|high)$|^back\d+$")


def edge_file(name: str, slugs: dict) -> tuple | None:
    """(number, tag, area) of an edges run's download named as Walk.reg names it ("01063_edge-base-custom-1.DAT": its
    tag, then the area's slug), the area by `slugs` ({slug: label}), the tag one EDGE_TAG names (so "spot-m" is never
    read off "tracking-spot-m"); None for any other file."""
    m = EDGE_FILE.match(name)
    if not m:
        return None
    for s, label in slugs.items():
        if m.group(2).endswith(f"-{s}") and EDGE_TAG.match(m.group(2)[:-len(s) - 1]):
            return int(m.group(1)), m.group(2)[:-len(s) - 1], label
    return None


def files_lines(run_dir: Path, lines: list, doc: dict) -> tuple:
    """([line], [said]) for the areas an --edges run stopped in before it wrote their line (a STOP before 2026-11-17
    wrote none): each edge-base download in its dat/ that no line's files name. Its registrations are that area's
    downloads after it, up to the next area's start; "values" each one's place records (those that changed between
    them, the start among them, as Walk.values reads them); its state the run's last line before it (context, grip),
    else its setup.jsonl's last setup before it where that put Switch V/H AF Area = Off (the camera level, its AF Frame
    Move Amt from its steps); "from_files": True. An area with two such starts, or whose state the files do not tell,
    is said and left out."""
    from camkit import camset
    from prove_run import held_value
    slugs = {slug(t["label"]): t["label"] for t in plan(doc, "all")}
    named = {f for ln in lines for f in (ln.get("files") or {}).values() if isinstance(f, str)}
    found = sorted((x, p.name) for p in (run_dir / "dat").glob("*.DAT") if (x := edge_file(p.name, slugs)))
    starts = [(x, name) for x, name in found if x[1] == "base" and name not in named]
    out, said = [], []
    for label in dict.fromkeys(x[2] for x, _ in starts):
        mine = [(x, name) for x, name in starts if x[2] == label]
        if len(mine) > 1:
            said.append(f"{label}: {len(mine)} starts no line names ({', '.join(n for _, n in mine)}): which one is the "
                        "owner's is not known; check its place by hand")
            continue
        (n0, _, _), base_name = mine[0]
        after = [x[0] for x, _ in found if x[1] == "base" and x[0] > n0]
        end = min(after) if after else None
        regs = [(x[1], name) for x, name in found if x[2] == label and x[0] >= n0 and (end is None or x[0] < end)]
        before = [ln for ln in lines if ln.get("area") and edge_number(ln) is not None and edge_number(ln) < n0]
        state = ({**{k: before[-1][k] for k in ("context", "grip", "mode", "memory_set") if before[-1].get(k)},
                  "state_from": f"the run's line before it ({before[-1]['area']})"} if before else
                 setup_state(run_dir, n0))
        if state is None:
            said.append(f"{label}: stopped at its start {base_name}, and the run's files do not say how the camera was "
                        "set (no line before it, no setup with Switch V/H AF Area = Off): check its place by hand")
            continue
        cs = {tag: camset.read(run_dir / "dat" / name) for tag, name in regs}
        tags = list(cs)
        keys = []
        for x, y in zip(tags, tags[1:], strict=False):
            keys += [c.key for c in camset.diff(cs[x], cs[y]) if c.key not in keys
                     and not isinstance(c.before, list) and not isinstance(c.after, list)]
        code = next(t["code"] for t in plan(doc, "all") if t["label"] == label)
        out.append({"area": label, "code": code, "moved": True, "from_files": True, "files": dict(regs),
                    "values": {tag: {k: held_value(cs[tag], k) for k in keys} for tag in tags}, **state})
    return out, said


def edge_number(line: dict) -> int | None:
    """The number of an edges line's start download (its files' "base"), None where it names none."""
    m = EDGE_FILE.match(str((line.get("files") or {}).get("base") or ""))
    return int(m.group(1)) if m else None


def setup_state(run_dir: Path, n0: int) -> dict | None:
    """The state an edges run's setup.jsonl says it worked in before download number `n0`: its last setup whose
    download came before it, where that put Switch V/H AF Area = Off ({"context": "Switch V/H AF Area Off, camera
    level" and its AF Frame Move Amt}); None otherwise (a grip's setup does not say how the camera was held)."""
    def number(name):
        m = re.match(r"^(\d+)_", str(name or ""))
        return int(m.group(1)) if m else None
    rows = [r for r in jsonl.read(run_dir / "setup.jsonl") if (number(r.get("after")) or 0) < n0] \
        if (run_dir / "setup.jsonl").exists() else []
    if not rows or f"{VH_ROW} = {OFF}" not in (rows[-1].get("steps") or []):
        return None
    amt = next((s.split(" = ", 1)[1] for s in rows[-1]["steps"] if s.startswith(f"{AMT_ROW} = ")), None)
    return {"context": context_of(None, amt), "state_from": "the run's setup.jsonl (no line before it)"}


def ratio_of(index: dict, cs) -> str | None:
    """The Aspect Ratio a settings file holds, by the definition's label for its code (the record the row's proof names,
    afreg_run.row_record: the a1 II's global:0x01fe); None where the definition or the file does not say it."""
    from prove_run import held_value
    rec = afreg_run.row_record(index, [RATIO_ROW])
    if rec is None or cs is None:
        return None
    return {v: str(lab) for v, lab in rec.get("values") or []}.get(held_value(cs, rec["key"]))


def at_centre(base: dict, index: dict) -> bool:
    """Whether a start holds the grid's centre in every place record (GRID_CENTRE by its name's X or Y): the centre at
    any Aspect Ratio."""
    for k, v in base.items():
        ax = axis_of((index.get(def_key(k)) or {}).get("name"))
        if ax is None or v != GRID_CENTRE[ax]:
            return False
    return bool(base)


def ratio_refusal(measured: str | None, now: str | None, base: dict, index: dict) -> str | None:
    """Why a put-back of a start `base` measured under Aspect Ratio `measured` is refused on a camera now on `now`
    (the run's start download); None when it may go. The place grid is stretched over the recorded picture, so a place
    off the centre has other numbers at another ratio: such a start is put back only under the ratio it was measured
    in, both read; a start at the centre (at_centre) is the centre at any ratio."""
    if at_centre(base, index):
        return None
    if measured is None or now is None:
        return (f"its start is off the centre and the {RATIO_ROW} it was measured under, or the camera's now, could not "
                "be read: a place off the centre has other numbers at another ratio")
    if measured != now:
        return (f"its start is off the centre and was measured under {RATIO_ROW} {measured}, the camera is on {now}: a "
                f"place off the centre has other numbers at another ratio; put it back with {RATIO_ROW} {measured}")
    return None


def put_back_area(cam, link, hdmi, run, cycle, model, labels, axes, t: dict, r: tuple, a, index: dict, turned,
                  src: dict, m: dict) -> dict:
    """One area of --put-back under Standard (the setup's): chosen; slot 1 registered where its frame is now (now); if
    the measured records already hold the start's, nothing pressed; else pushed Right and Down to the far corner
    (high), registered, and brought back by edge_way_back from there (Walk.way_back), each landing registered and
    checked on the measured records alone against the start's registration in the edges run `src` (the start's file
    holds that run's AF Frame Move Amt, this one's Standard). A failure leaves the frame where it is: a run again starts
    from wherever that is."""
    from prove_run import Failed, to_shooting
    from runner import close_screen
    w = Walk(cam, link, hdmi, run, cycle, model, a, turned, t, "put", {"now": "Standard"})
    keys = [rec["key"] for rec in src["edges"]] if src.get("edges") else m["h"]["keys"] + m["v"]["keys"]
    base = {k: src["values"]["base"][k] for k in keys}
    w.line.update(source={"run": a.put_back, "start": src["files"].get("base"), "context": src.get("context"),
                          **({"from_files": True} if src.get("from_files") else {})})

    def check(tag):
        return [{"key": k, "delta": v - base[k]} for k, v in w.held(tag, keys).items() if v != base[k]]
    try:
        got = afreg_run.choose_area(cam, run, cycle, model, labels, axes, r, turned)
        w.frames.update(chosen=got["chosen_frame"], after_ok=got["row_frame"])
        to_shooting(link, hdmi, "the shooting screen with the area chosen")
        w.reg("now")
        now = w.held("now", keys)
        w.line["values"] = {"now": now}
        if not check("now"):
            w.line["back"] = {"same": True, "off": [], "tries": 0, "presses": [], "under": "Standard", "already": True}
            return w.line
        w.pushed([["ms_right", a.edge_presses], ["ms_down", a.edge_presses]])
        w.reg("high")
        high = w.line["values"]["high"] = w.held("high", keys)
        far = [{"key": k, "delta": high[k] - src["values"]["high"][k]} for k in keys
               if src["values"].get("high", {}).get(k) is not None and high[k] != src["values"]["high"][k]]
        if far:
            w.line["far_off"] = far                 # the far corner reads otherwise than the edges run's
        w.way_back(high, base, m, check, keys)
    except Failed as e:
        w.line["failed"] = str(e)
        close_screen(cam, link)
    return w.line


def put_back_summary_of(line: dict) -> list:
    """A --put-back line in words: put back or not, the difference by key where not; never a place."""
    head = f"{line['area']} (code {line.get('code')}" + (f"; {line['context']})" if line.get("context") else ")")
    n = line.get("memory_set", 1)
    src = line.get("source") or {}
    out = [f"{head}: to its start in {src.get('run')} ({src.get('start')})"]
    if line.get("refused"):
        return out + [f"    NOT PUT BACK, nothing pressed: {line['refused']}"]
    if line.get("far_off"):
        out.append("    the far corner read otherwise than the edges run's: "
                   + "; ".join(f"{shown_key(x['key'], n)} {x['delta']:+d}" for x in line["far_off"]))
    if line.get("failed"):
        out.append(f"    failed: {line['failed']}")
    back = line.get("back")
    if back and back["same"]:
        out.append("    already where it began: nothing pressed" if back.get("already") else
                   "    put back under Standard: the registration after it matched the start's on the measured records")
    elif back:
        off = "; ".join(f"{shown_key(x['key'], n)} {x['delta']:+d}" for x in back.get("off") or []) or "its place unknown"
        out.append(f"    NOT PUT BACK: {off} off: on the shooting screen with {ROW} = {line['area']}, move it back by "
                   "hand")
    elif line.get("moved"):
        out.append(f"    ITS FRAME MAY BE MOVED: run --put-back {src.get('run')} again, or move it back by hand")
    else:
        out.append("    its frame was not moved")
    return out


def put_back_loop(s, a, run, hdmi, cycle, model, labels, axes, todo, routes, index, tag, lines, setup, turned):
    """--put-back's session body after the setup: each area put back (put_back_area), its line written to
    put_back.jsonl and said; an area not put back ends the run. An area whose start is off the centre and was measured
    under another Aspect Ratio than the camera's now (ratio_refusal: the source's "start_ratio", this run's start
    download's, a.ratio_now) is refused before it is chosen, nothing pressed, said, and the run goes on."""
    for t in todo:
        src, m = a.put_back_lines[t["label"]]
        why = ratio_refusal(src.get("start_ratio"), getattr(a, "ratio_now", None), src["values"]["base"], index)
        if why:
            line = {"t": round(time.time(), 3), "area": t["label"], "code": t["code"], "refused": why,
                    "source": {"run": a.put_back, "start": src["files"].get("base"), "context": src.get("context")},
                    **tag, "setup": setup}
            jsonl.append(run.dir / "put_back.jsonl", line)
            lines.append(line)
            print("\n".join(put_back_summary_of(line)), flush=True)
            continue
        try:
            line = put_back_area(s.cam, s.link, hdmi, run, cycle, model, labels, axes, t, routes[t["label"]], a,
                                 index, turned, src, m)
        except BaseException:
            print(f"  {t['label']}: stopped with its frame perhaps moved: run --put-back {a.put_back} again", flush=True)
            raise
        line.update(tag, setup=setup)
        jsonl.append(run.dir / "put_back.jsonl", line)
        lines.append(line)
        print("\n".join(put_back_summary_of(line)), flush=True)
        if not (line.get("back") or {}).get("same"):
            print(f"{t['label']} is not put back: stopping", flush=True)
            break


def prove(a, doc: dict, todo: list, focus: bool, drive: bool, context: str, allowance: str, amt: str | None = None) -> int:
    from camkit.frames import eyes_from_config
    from camkit.runs import Run
    from mode_switch import MAY_OPEN
    from pass3_run import labels_of
    from prove_run import AXES
    from runner import load_scan, prover_session, write_text
    mode, mp = getattr(a, "mode", "Stills"), getattr(a, "map", None)
    where = paths.shown(Path(mp)) if mp else "pass 1's map"         # another mode's map: main's (mode_map, --map)
    labels, kind = labels_of([ROW], mp) if mp else labels_of([ROW])
    if kind != "dialog":
        sys.exit(f"{ROW} is a {kind} in {where}, not a carousel")
    axes = {o: info for o, info in read_json(AXES).get(ROW, {}).items() if len(info["values"]) > 1}
    routes = {t["label"]: afreg_run.route(t["label"], labels, axes) for t in todo + ([a.zone_target] if a.zone_grid else [])}
    lost = [lab for lab, r in routes.items() if r is None]
    if lost:
        sys.exit(f"{where} and the axis walk ({AXES}) do not name {lost} once: walk the axes first "
                 "(kit/axis_walk.py --rows 'Focus Area')")
    index = {s["key"]: s for s in doc.get("settings") or []}
    cycle, model = load_scan(a.scan)
    run = Run(a.run)
    if turned_of(a.grip):
        (run.dir / "upright").mkdir(exist_ok=True)          # the turned frames read upright (orient_run.upright)
    hdmi = eyes_from_config(run)
    out = run.dir / "framepos.jsonl"
    tag = {"context": context, **({"allowance": allowance} if allowance else {}),
           **({"grip": a.grip} if a.grip else {}), **({"upright": True} if turned_of(a.grip) else {}),
           **({"mode": mode} if mode != "Stills" else {})}
    # a zone moves by its own one-step moves (the sweep by its route), never by --moves: its lines carry the context a
    # run without --moves gives, so they match a default run's
    zone_tag = dict(tag, context=context_of(a.context, amt, None, a.grip, mode=mode))
    lines = []
    may_open = set(a.allow) | (set(MAY_OPEN) if focus or drive else set())
    # the registration records of the set registered, which no settings file sets back (slot 1's EXPECTED_LEFT in
    # Stills, Movie Memory 1's in Movie); S&Q's once the start download names its family (areas: run_set)
    n = getattr(a, "memory_set", 1)
    a.expected = set(slot_records(n)) if n else set()
    try:
        with prover_session(run, hdmi, may_open=may_open, show=0, expected=a.expected,
                            end_why="the settings download after the frames") as s:
            areas(s, a, run, hdmi, cycle, model, labels, axes, todo, routes, index, focus, drive, out, tag, lines, amt,
                  zone_tag)
    finally:
        if out.exists():
            summary = summary_lines(jsonl.read(out))
            write_text(run.dir / "framepos_summary.txt", "\n".join(summary) + "\n")
        if getattr(a, "put_back", None):
            found = sum(1 for ln in lines if (ln.get("back") or {}).get("same"))
            print(f"frames put back where {a.put_back} began them: {found} of {len(todo)} "
                  f"({paths.shown(run.dir / 'put_back.jsonl')})", flush=True)
        elif getattr(a, "edges", False):
            found = sum(1 for ln in lines if ln.get("edges") and not ln.get("failed") and ln["back"]["same"])
            print(f"areas whose edges were measured, their frame back where it began: {found} of {len(todo)} "
                  f"(summary: {paths.shown(run.dir / 'edges_summary.txt')})", flush=True)
        else:
            found = sum(1 for ln in lines if ln.get("changed"))
        if todo and not getattr(a, "edges", False) and not getattr(a, "put_back", None):
            print(f"areas whose frame's place showed in the registrations: {found} of {len(todo)} "
                  f"(summary: {paths.shown(run.dir / 'framepos_summary.txt')})", flush=True)
        sweeps = [ln for ln in lines if ln.get("sweep")]
        if a.zone_grid:
            print(f"zone grid sweep: {sum(ln.get('confirmed', 0) for ln in sweeps)} of 9 places confirmed "
                  f"({paths.shown(run.dir / 'zone_grid.jsonl')})", flush=True)
    swept = all(ln.get("confirmed") == 9 and ln.get("back_same") for ln in sweeps) and len(sweeps) == 1 \
        if a.zone_grid else True
    return 0 if found == len(todo) and swept else 1


def areas(s, a, run, hdmi, cycle, model, labels, axes, todo, routes, index, focus, drive, out, tag, lines, amt=None,
          zone_tag=None):
    """The session's body: slot 1 checked filled in the start file, the setup, then every area of the plan (one_area),
    each area's line written and summed up as it comes; three areas failing in a row end it, and
    held vertically (a.grip down or up) one does, its frame put back first: the owner is holding the camera. Held
    vertically, Vertical Display is read from the start download (afreg_run.screens_held, kept as a.vertical): Off reads
    every screen level and drops "upright" from the lines; On or Off ends their context's grip with "Vertical Display
    On" or "Vertical Display Off". A zone's line, and the sweep's, carry `zone_tag` (the context without --moves, which
    a zone never takes) in place of `tag`. In Movie or S&Q (a.mode) the slot is that mode's (run_set: Movie Memory 1,
    memory set 4 on the a1 II; S&Q's by the start download's family), checked filled, its records added to the restore
    check's (a.expected) and the set to every line ("memory_set"); a --put-back's source lines must name the same set."""
    zone_tag = zone_tag or tag
    from camkit import camset
    from prove_run import Failed
    from runner import close_screen
    cam, link = s.cam, s.link
    grip, mode = getattr(a, "grip", None), getattr(a, "mode", "Stills")
    start = camset.read(s.start)
    n = a.memory_set = run_set(a, index, start)
    if not slot_filled(start, n):
        if mode == "Stills" and n == 1:
            raise Failed("slot 1 is empty in the start file: registering it would mark it filled for good (no settings "
                         "file empties it); this run registers a filled slot only")
        name = memory_name({"camera": {"memory_sets": getattr(a, "memory_sets", None) or {}}}, n)
        raise Failed(f"{name} (memory set {n}) is empty in the start file: registering it would mark it filled for good "
                     "(no settings file empties it); this run registers a filled slot only. Filling it is the owner's "
                     f"choice: registered once by hand ({MEMORY_ROW}, slot 1, in {mode} mode), a run can go")
    if getattr(a, "expected", None) is not None:
        a.expected.update(slot_records(n))
    if mode != "Stills":
        tag["memory_set"] = zone_tag["memory_set"] = n
    if getattr(a, "put_back", None):
        other = sorted({ln.get("memory_set", 1) for ln, _ in (getattr(a, "put_back_lines", None) or {}).values()} - {n})
        if other:
            raise Failed(f"{a.put_back}'s lines registered memory set {other[0]}, this run memory set {n}: a frame is put "
                         "back in the mode and family it was measured in")
        a.ratio_now = ratio_of(index, start)        # the Aspect Ratio a start off the centre is put back under
    turned, a.vertical, said = afreg_run.screens_held(grip, index, start)
    if said:
        print(f"  {said}", flush=True)
    if a.vertical:                                  # On or Off, as the start download holds it
        moves = parse_moves(a.moves) if getattr(a, "moves", None) else None
        for tg, mv in ((tag, moves), (zone_tag, None)):
            tg["context"] = context_of(getattr(a, "context", None), amt, mv, grip, a.vertical, mode)
            if not turned:                          # Off: every screen read level
                tg.pop("upright", None)
    edges, putting = getattr(a, "edges", False), bool(getattr(a, "put_back", None))
    upright_sweep = bool(getattr(a, "zone_grid", False)) and grip in TURNED      # the zone held vertically: edges stop it
    setup = prepare(cam, link, hdmi, run, cycle, model, focus, drive, s.start, amt, index, grip,
                    circ=edges or putting or upright_sweep, vh=getattr(a, "vh", True))
    if putting:
        put_back_loop(s, a, run, hdmi, cycle, model, labels, axes, todo, routes, index, tag, lines, setup, turned)
        return
    if edges:
        edge_loop(s, a, run, hdmi, cycle, model, labels, axes, todo, routes, index, tag, lines, setup, turned, amt)
        return
    if a.zone_grid:
        zone_grid(s, a, run, hdmi, cycle, model, labels, axes, routes, index, out, zone_tag, lines, setup)
    in_a_row = 0
    for t in todo:
        owed, failed = [], False
        try:
            line = one_area(cam, link, hdmi, run, cycle, model, labels, axes, t, routes[t["label"]], a, index, owed)
            in_a_row = 0
        except Failed as e:
            print(f"  {t['label']}: {e}", flush=True)
            close_screen(cam, link)
            line = {"t": round(time.time(), 3), "area": t["label"], "code": t["code"], "failed": str(e)}
            failed = True
            if owed:                                # the frame is moved: put it back before the next area
                sent, done = [], []
                try:
                    press_moves(cam, owed, sent, done, turned, run)
                except Failed as e2:
                    line["put_back_failed"] = str(e2)
                    print(f"  {t['label']}: the frame could not be put back ({e2}): on the shooting screen with "
                          f"{ROW} = {t['label']}, press {say_moves(left_to_send(owed, done))} by hand", flush=True)
                    close_screen(cam, link)
                line["put_back"], line["put_back_sent"] = done, sent
            in_a_row += 1
        except BaseException:
            if owed:                                # the session's own end takes it from here: say what is owed
                print(f"  {t['label']}: its frame is moved; on the shooting screen with {ROW} = {t['label']}, "
                      f"press {say_moves(owed)} by hand to put it back", flush=True)
            raise
        line.update(zone_tag if gridded(t["label"]) else tag, setup=setup)
        jsonl.append(out, line)
        lines.append(line)
        print("\n".join(summary_of(line)), flush=True)
        if failed and grip in TURNED:
            print(f"held vertically (grip {grip}), a failed area ends the run: stopping", flush=True)
            break
        if in_a_row == 3:
            print("three areas in a row failed: stopping", flush=True)
            break


def zone_grid(s, a, run, hdmi, cycle, model, labels, axes, routes, index, out, tag, lines, setup):
    """The zone grid sweep (zone_sweep) with its failure handled as an area's is: the screen closed and the frame put
    back by the presses owed; its line is written to framepos.jsonl (no "area": the summary leaves it)."""
    from prove_run import Failed
    from runner import close_screen
    cam, link = s.cam, s.link
    t, owed = a.zone_target, []
    try:
        line = zone_sweep(cam, link, hdmi, run, cycle, model, labels, axes, t, routes[t["label"]], a, index, owed, tag)
    except Failed as e:
        print(f"  zone sweep: {e}", flush=True)
        close_screen(cam, link)
        line = {"t": round(time.time(), 3), "sweep": "zone-grid", "failed": str(e), **tag}
        if owed:
            sent, done = [], []
            try:
                press_moves(cam, owed, sent, done, turned_of(getattr(a, "grip", None), getattr(a, "vertical", None)),
                            run)
            except Failed as e2:
                line["put_back_failed"] = str(e2)
                print(f"  zone sweep: the frame could not be put back ({e2}): on the shooting screen with {ROW} = Zone, "
                      f"press {say_moves(left_to_send(owed, done))} by hand", flush=True)
                close_screen(cam, link)
    except BaseException:
        if owed:
            print(f"  zone sweep: the frame is moved; on the shooting screen with {ROW} = Zone, press "
                  f"{say_moves(owed)} by hand to put it back", flush=True)
        raise
    line.update(setup=setup)
    jsonl.append(out, line)
    lines.append(line)


def mode_setup(a, doc: dict, index: dict) -> None:
    """What a run needs of its shooting mode (a.mode, the --scan's: scan_for) before anything connects, kept on `a`: the
    memory set it registers (a.memory_set: the mode's first, memory_set; None in S&Q until the start download names the
    family, run_set; slot 1's set 1 in Stills, as always), the map it plans Focus Area from (a.map: --map, else
    mode_map; pass 1's in Stills), and the setup rows the mode does not offer (a.absent, absent_rows), Switch V/H AF Area
    among them where the mode has none (a.vh). Stops where the definition numbers no memory set for the mode, or no
    crawl of the mode maps Focus Area and --map names none."""
    a.memory_sets = (doc.get("camera") or {}).get("memory_sets") or {}
    a.absent, a.vh = {}, True
    if a.mode == "Stills":
        a.memory_set = memory_set(doc, "Stills") or 1
        return
    a.memory_set = None if a.mode == "S&Q" else memory_set(doc, a.mode)
    if memory_set(doc, a.mode) is None:
        sys.exit(f"framepos_run: the definition numbers no memory set for {a.mode} mode (its camera section's "
                 f"memory_sets), so the run could not tell which slot a registration in {a.mode} mode writes: nothing "
                 "was sent to the camera")
    a.map = a.map or mode_map(a.mode)
    if not a.map:
        sys.exit(f"framepos_run: no crawl of {a.mode} mode maps {ROW} (a kit2_crawl* run named for the mode, whose map.json "
                 f"has the row), and a run in {a.mode} mode plans from that mode's own map: map it in {a.mode} mode first "
                 f"(kit/crawl_run.py --start-label '{ROW}' --limit 1 with this mode's page scan, then kit/pass1_labels.py, "
                 "kit/tiebreak.py and kit/pass1_map.py --own, as kit/prove_run.py's notes say), or name a map that has it "
                 "with --map <run>/map.json. Nothing was sent to the camera.")
    a.absent = absent_rows(a.mode, index, scan_rows(a.scan),
                           [VH_ROW, CIRC_ROW, AMT_ROW, afreg_run.FOCUS_ROW, afreg_run.DRIVE_ROW])
    a.vh = VH_ROW not in a.absent


def plan_map(a) -> tuple:
    """(the carousel's labels, the second axes) Focus Area is planned from: the run's map (a.map: mode_setup's; pass 1's
    in Stills unless --map names one) and the axis walk's axes (kit2_axes, walked in Stills: each axis step is read on
    the camera as it is taken, so an axis another mode draws otherwise fails there, never chooses another area). In
    Stills (None, None) where either cannot be read, the plan printed without its routes (prove stops on them); in
    another mode its map must have the row, and no axis walk leaves the axes empty."""
    from pass3_run import labels_of
    from prove_run import AXES
    if a.mode == "Stills":
        try:
            labels, _ = labels_of([ROW], a.map) if a.map else labels_of([ROW])
            return labels, {o: info for o, info in read_json(AXES).get(ROW, {}).items() if len(info["values"]) > 1}
        except (SystemExit, OSError, ValueError):
            return None, None
    try:
        labels, _ = labels_of([ROW], a.map)
    except (SystemExit, OSError, ValueError, TypeError):
        sys.exit(f"framepos_run: {paths.shown(Path(a.map))} has no {ROW} row this run can plan from. Nothing was sent to "
                 "the camera.")
    try:
        axes = {o: info for o, info in read_json(AXES).get(ROW, {}).items() if len(info["values"]) > 1}
    except (SystemExit, OSError, ValueError):
        axes = {}
    return labels, axes


def refuse_absent(a, needed: list) -> None:
    """Stops, before anything connects, a run whose setup sets a row its mode does not offer (a.absent)."""
    lost = [r for r in needed if r in getattr(a, "absent", {})]
    if lost:
        sys.exit(f"framepos_run: {lost[0]} is not on {a.mode} mode's menu ({a.absent[lost[0]]}), and this run sets it: "
                 f"not in {a.mode} mode as asked. Nothing was sent to the camera.")


def mode_said(a) -> list:
    """The plan's lines on the mode's setup: Switch V/H AF Area left as it is where the mode does not offer it."""
    why = getattr(a, "absent", {}).get(VH_ROW)
    return [f"  {VH_ROW} left as the camera has it: {a.mode} mode does not offer it ({why})"] if why else []


def put_back_main(a) -> int:
    """--put-back RUN: the frames RUN's edges.jsonl leaves out of place (left_behind), each with what its line gives to
    bring it back (put_back_plan; an area it cannot is said and left out), held as RUN held the camera (its lines'
    "grip"), the plan printed; with the owner's word for Camera Set. Memory, the session (prove: the setup puts Switch
    V/H AF Area as the grip has it, Circ. of Focus Point and AF Frame Move Amt Standard; put_back_loop)."""
    for flag, given in (("--edges", a.edges), ("--zone-grid", a.zone_grid), ("--moves", a.moves is not None),
                        ("--areas", a.areas is not None)):
        if given:
            sys.exit(f"framepos_run: --put-back with {flag}: a put-back brings back the frames {a.put_back}'s lines name")
    if a.frame_move_amt not in (None, "Standard"):
        sys.exit(f"framepos_run: --put-back is made under {AMT_ROW} Standard, where the way back is proved")
    from camkit import camset
    run_dir = paths.run_root() / a.put_back
    lines = jsonl.read(run_dir / "edges.jsonl")
    doc = definitions.with_evidence(read_json(definitions.active()), definitions.active())
    index = {s["key"]: s for s in doc.get("settings") or []}
    on_disk, said = files_lines(run_dir, lines, doc) if (run_dir / "dat").is_dir() else ([], [])
    for x in said:
        print(f"  {x}", flush=True)
    src, twice = [], {ln["area"] for ln in on_disk} & {ln["area"] for ln in left_behind(lines)}
    for ln in left_behind(lines) + on_disk:
        if ln["area"] in twice:
            if ln.get("from_files"):
                print(f"  {ln['area']}: a line not back and a start no line names: which start is the owner's is not "
                      "known; check its place by hand", flush=True)
            continue
        src.append(ln)
    if not src:
        print(f"no frame of {a.put_back} is left out of place: its edges.jsonl says each came back, or names none")
        return 0
    grips = {ln.get("grip") for ln in src}
    if len(grips) > 1 or (a.grip and a.grip not in grips):
        sys.exit(f"framepos_run: --put-back {a.put_back}: its lines were made held {sorted(map(str, grips))}"
                 + (f", not --grip {a.grip}" if a.grip else "") + ": one way at a time, the run's own")
    a.grip = grips.pop()
    modes = sorted({ln.get("mode", "Stills") for ln in src})
    if modes != [a.mode]:
        sys.exit(f"framepos_run: --put-back {a.put_back}: its lines were made in {' and '.join(modes)} mode, and this "
                 f"run works in {a.mode} mode (its --scan's): a frame is put back in the mode it was measured in, with "
                 f"--scan naming a page scan of that mode")
    mode_setup(a, doc, index)
    todo, a.put_back_lines = [], {}
    for ln in src:
        m, why = put_back_plan(ln, index=index)
        if m is None:
            print(f"  {ln['area']}: not put back: {why}; move it back by hand", flush=True)
            continue
        base = run_dir / "dat" / str((ln.get("files") or {}).get("base"))
        try:
            ln["start_ratio"] = ratio_of(index, camset.read(base)) if base.is_file() else None
        except Exception:                   # a download that cannot be read: the ratio is not known
            ln["start_ratio"] = None
        t = plan(doc, ln["area"])[0]
        todo.append(t)
        a.put_back_lines[t["label"]] = (ln, m)
    want, stops = amt_code(index, "Standard"), setting_code(index, [CIRC_ROW], CIRC_OFF)
    if want is None or stops is None:
        sys.exit(f"framepos_run: --put-back: the definition gives no code for {AMT_ROW} = Standard or {CIRC_ROW} = "
                 f"{CIRC_OFF}, so the run could not check the camera took them")
    context = context_of(a.context, "Standard", None, a.grip, mode=a.mode)
    print(f"{len(todo)} frames {a.put_back} left out of place, to be put back ({context!r}; run {a.run}):", flush=True)
    for t in todo:
        ln = a.put_back_lines[t["label"]][0]
        print(f"  {t['label']} (code {t['code']}): to its start registration in {a.put_back} "
              f"({ln['files'].get('base')}), measured under {ln.get('context')!r}", flush=True)
        if ln.get("from_files"):
            print(f"    taken from the run's files: it stopped before writing this area's line; its place records are "
                  f"those that changed between {', '.join(ln['files'].values())}, its state {ln.get('state_from')}",
                  flush=True)
        centre = at_centre(ln["values"]["base"], index)
        if ln.get("start_ratio") or not centre:
            print(f"    measured under {RATIO_ROW} {ln.get('start_ratio') or '(not read)'} (its start download): "
                  + ("its start is the centre, the centre at any ratio" if centre else
                     "its start is off the centre, so it is put back only where the camera's start download reads "
                     "that ratio, else refused, nothing pressed"), flush=True)
    tracking = any(t["tracking"] for t in todo)
    focus = a.focus_mode == "menu" or (a.focus_mode == "auto" and tracking)
    drive = a.drive_mode == "menu" or (a.drive_mode == "auto" and tracking)
    refuse_absent(a, [CIRC_ROW, AMT_ROW] + ([afreg_run.FOCUS_ROW] if focus else []) + ([afreg_run.DRIVE_ROW] if drive else []))
    sets = [afreg_run.step_name(k, w) for k, w in setup_steps(focus, drive, "Standard", a.grip, True, a.vh)]
    print(f"set through the menu first: {'; '.join(sets)}; the start file put back at the end puts them back (a "
          "frame's place is in no settings file: the restore leaves it where it is put)", flush=True)
    for said in mode_said(a):
        print(said, flush=True)
    print(f"the download after the setup must hold Standard's code {want[1]} in {want[0]} and {CIRC_OFF}'s code "
          f"{stops[1]} in {stops[0]}, or the run stops before any area", flush=True)
    if afreg_run.vertical_plan(a.grip, index):
        print(afreg_run.vertical_plan(a.grip, index), flush=True)
    print(f"each area: slot 1 registered ({MEMORY_ROW}) where its frame is now; at its start already, nothing pressed; "
          f"else pushed {a.edge_presses} Right and Down to the far corner, registered, brought back by presses counted "
          "from there in Standard's step (the hand tables' FRAME_STEPS) and registered, which must match the start's "
          f"registration on the measured records, up to {EDGE_TRIES} more to make good a press the camera lost; a start "
          "no press reaches is said, nothing more pressed, and the run stops there", flush=True)
    if a.list or not todo:
        return 0
    if not memory_allowed(a.allow):
        sys.exit(f"registering slot 1 opens {MEMORY_ROW}, a never-open action row (camkit.safety): it is opened only "
                 f"with the owner's word, --allow {MEMORY_ROW!r}")
    others = [x for x in a.allow if not memory_allowed([x])]
    if others:
        sys.exit(f"framepos_run: --allow names {others}: this run opens no never-open row but {MEMORY_ROW}")
    a.zone_target = None
    return prove(a, doc, todo, focus, drive, context, allowed_or_exit(a.allow), amt="Standard")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--areas", default=None,
                    help="default (the fourteen movable areas of DEFAULT_AREAS; what runs when neither this nor "
                         "--zone-grid is given), all, or the definition's labels, comma-separated ('Zone,Spot: S')")
    ap.add_argument("--zone-grid", action="store_true",
                    help="sweep the Zone's nine grid places, slot 1 registered at each (zone_grid.jsonl); alone it runs "
                         "this sweep only, with --areas the sweep first, then those areas; level with Switch V/H AF Area "
                         "Off, or held as --grip down or up says")
    add_allow_argument(ap)
    ap.add_argument("--focus-mode", choices=("auto", "menu", "leave"), default="auto",
                    help="auto: Focus Mode = Continuous AF through the menu (its dial set with the menu) when the plan "
                         "holds a Tracking area; menu: always; leave: as the camera has it")
    ap.add_argument("--drive-mode", choices=("auto", "menu", "leave"), default="auto",
                    help="auto: Drive Mode Dial = Set with Menu and Drive Mode = Single Shooting when the plan holds a "
                         "Tracking area (the camera refuses Continuous AF under some drive modes); menu: always; "
                         "leave: as it is")
    ap.add_argument("--frame-move-amt", choices=("Standard", "Large", "leave"), default=None,
                    help="Standard or Large: AF Frame Move Amt put on it through the menu with the other setup rows, so "
                         "the step a press moves the frame can be measured under it; leave: as the camera has it "
                         "(the default, but with --edges, whose default is Standard)")
    ap.add_argument("--edges", action="store_true",
                    help="measure how far each frame can travel: pushed to its edges and brought back exactly, its "
                         "edges and step per press read from slot 1's registrations (edges.jsonl, edges_summary.txt); "
                         "every movable area but the zones unless --areas names some")
    ap.add_argument("--edge-presses", type=int, default=EDGE_PRESSES,
                    help=f"--edges: the presses a push toward an edge takes, ten to ninety-nine (default {EDGE_PRESSES})")
    ap.add_argument("--put-back", metavar="RUN", default=None,
                    help="bring back each frame an --edges run left out of place (its edges.jsonl says it moved and is "
                         "not back) to that run's start registration, under AF Frame Move Amt Standard through the far "
                         "corner, held as that run held the camera; checked on the measured records")
    ap.add_argument("--moves", default=None,
                    help="the presses that move a point or box area's frame in place of Left 3, Up 2: a direction (Left, "
                         "Right, Up, Down) and one to nine presses, comma-separated in the order taken ('Right 1', "
                         "'Left 1,Up 1'); a direction once, never with its opposite. For a frame near the limit of its "
                         "travel; Zone and Tracking: Zone keep their one-step moves")
    ap.add_argument("--check-back", action=argparse.BooleanOptionalAction, default=True,
                    help="register slot 1 once more after the frame is put back and check it matches the first "
                         "(default; --no-check-back skips it)")
    ap.add_argument("--grip", choices=GRIPS, default=None,
                    help="down or up: the owner holds the camera vertically: Switch V/H AF Area = AF Point + AF Area, "
                         "that orientation's copies, the turned dialog read upright; level: the same setting with the "
                         "camera standing level, the level copies, every screen read level")
    add_scan_argument(ap, default=LATEST_SCAN, mode="Stills")
    ap.add_argument("--map", default=None, type=paths.run_arg,
                    help="the map Focus Area is planned from (a run's map.json in the camera's runs): by default pass 1's "
                         "in Stills, and in Movie or S&Q (a --scan made in that mode) the mode's own crawl's")
    ap.add_argument("--run", default=None, help="the run's folder (default kit2_framepos; with --edges kit2_framepos_edges)")
    ap.add_argument("--context", default=None, help="more of the state these registrations are made in")
    ap.add_argument("--limit", type=int, default=0, help="the first N areas of the plan only")
    ap.add_argument("--list", action="store_true", help="print the plan only; no camera")
    ap.add_argument("--summary", action="store_true", help="print what the run's lines found, deltas only; no camera")
    add_info_ok_argument(ap)    # Mode Dial Control Set's note before its table (afreg_run.focus_dial_by_menu: pass_note)
    a = ap.parse_args(argv)
    notes_named_or_exit(a.info_ok, [afreg_run.DIAL_ROW])
    a.run = a.run or ("kit2_framepos_put_back" if a.put_back else "kit2_framepos_edges" if a.edges else "kit2_framepos")
    if a.summary:
        got = edge_summary_lines(jsonl.read(paths.run_root() / a.run / "edges.jsonl")) if a.edges else \
            summary_lines(jsonl.read(paths.run_root() / a.run / "framepos.jsonl"))
        print("\n".join(got) if got else "no line in the run")
        return 0
    for flag, given, why in (("--zone-grid", a.zone_grid, "a zone's places are the nine --zone-grid proves"),
                             ("--moves", a.moves is not None, "an edge measure makes its own presses"),
                             ("--no-check-back", not a.check_back, "an edge measure always checks its frame is back")):
        if a.edges and given:
            sys.exit(f"framepos_run: --edges with {flag}: {why}")
    if (a.edges or a.put_back) and not 10 <= a.edge_presses <= 99:
        sys.exit(f"framepos_run: --edge-presses {a.edge_presses}: a push takes ten to ninety-nine presses")
    if a.edges and a.frame_move_amt == "leave":
        sys.exit("framepos_run: --edges with --frame-move-amt leave: the way back is made under Standard, and the run "
                 "must know which it measures under: Standard or Large")
    a.scan = scan_for(a.scan)           # the mode the run works in is its page scan's: Stills' latest by default
    a.mode = a.scan.mode
    if a.mode != "Stills":
        for flag, given, why in (("--grip", a.grip, f"the grip runs set {VH_ROW}, which {a.mode} mode does not offer"),
                                 ("--zone-grid", a.zone_grid, f"the sweep is made with {VH_ROW} Off, which {a.mode} mode "
                                  "does not offer, and reads slot 1's records in set 1: not made for another mode yet")):
            if given:
                sys.exit(f"framepos_run: {flag} in {a.mode} mode: {why}. Nothing was sent to the camera.")
    if a.put_back:
        return put_back_main(a)
    if a.zone_grid and a.grip == "level":
        sys.exit("framepos_run: --zone-grid with --grip level: the level sweep is made with Switch V/H AF Area Off, "
                 "without --grip; held vertically, --grip down or up")
    if a.zone_grid and not ZONE:
        sys.exit("framepos_run: --zone-grid plans and checks its sweep by the Zone grid's places, and the hand tables of "
                 "the camera the kit works on name none (ZONE in data/<model>_fw<fw>/hand_tables_<model>_fw<fw>.json; "
                 "docs/DATA_CONTRACTS.md, \"The hand tables file\"): nothing was touched")
    moves = parse_moves(a.moves) if a.moves is not None else None
    doc = definitions.with_evidence(read_json(definitions.active()), definitions.active())
    index = {s["key"]: s for s in doc.get("settings") or []}
    todo = edge_plan(doc, a.areas) if a.edges else \
        plan(doc, a.areas or "default", moves) if a.areas or not a.zone_grid else []
    a.zone_target = plan(doc, "Zone")[0] if a.zone_grid else None
    mode_setup(a, doc, index)
    labels, axes = plan_map(a)
    left = []
    if a.mode != "Stills":
        todo, left = offered(todo, labels, axes, map_labels(a.map, ["Focus Area Limit"]))
        if left and not todo:
            sys.exit(f"framepos_run: --areas {a.areas or 'all'}: {a.mode} mode offers none of them "
                     f"({', '.join(t['label'] for t in left)}; {paths.shown(Path(a.map))}). Nothing was sent to the "
                     "camera.")
    if a.limit:
        todo = todo[:a.limit]
    if moves and all(gridded(t["label"]) for t in todo):
        sys.exit(f"framepos_run: --moves {a.moves!r}: no area of the plan takes them (Zone and Tracking: Zone keep their "
                 "one-step moves, --zone-grid its route)")
    tracking = any(t["tracking"] for t in todo)
    focus = a.focus_mode == "menu" or (a.focus_mode == "auto" and tracking)
    drive = a.drive_mode == "menu" or (a.drive_mode == "auto" and tracking)
    if drive and a.grip in TURNED:
        sys.exit(f"framepos_run: held vertically (--grip {a.grip}) Drive Mode's chooser is drawn in the portrait "
                 "arrangement, which the kit cannot read (afreg_run.drive_single): give --drive-mode leave, Drive Mode "
                 "left as the camera has it")
    amt = a.frame_move_amt if a.frame_move_amt in ("Standard", "Large") else \
        "Standard" if a.edges and a.frame_move_amt is None else None
    want = amt_code(index, amt) if amt else None
    if amt and want is None:
        sys.exit(f"framepos_run: --frame-move-amt {amt}: the definition has no {AMT_ROW} record whose values name "
                 f"{amt!r}, so the run could not check that the camera took it")
    needs_circ = a.edges or (a.zone_grid and a.grip in TURNED)
    stops = setting_code(index, [CIRC_ROW], CIRC_OFF) if needs_circ else None
    if needs_circ and stops is None:
        sys.exit(f"framepos_run: {'--edges' if a.edges else '--zone-grid held vertically'}: the definition has no "
                 f"{CIRC_ROW} record proved by its row whose values name {CIRC_OFF!r}, so the run could not check that a "
                 "frame stops at its edge rather than wrapping round")
    if a.edges and amt == "Large":
        lacking = [t["label"] for t in todo if standard_step(t["label"]) is None]
        if lacking or amt_code(index, "Standard") is None:
            sys.exit(f"framepos_run: --edges under Large makes each way back under Standard, counted in Standard's step: "
                     f"the hand tables' FRAME_STEPS give none for {lacking}" if lacking else
                     f"framepos_run: --edges under Large: the definition gives no code for {AMT_ROW} = Standard")
    refuse_absent(a, ([CIRC_ROW] if needs_circ else []) + ([AMT_ROW] if amt else [])
                  + ([afreg_run.FOCUS_ROW] if focus else []) + ([afreg_run.DRIVE_ROW] if drive else []))
    context = context_of(a.context, amt, moves, a.grip, mode=a.mode)
    if a.edges:
        print(f"{len(todo)} areas' edges ({context!r}; run {a.run}):", flush=True)
    else:
        print(f"{len(todo)} areas{' and the zone grid sweep' if a.zone_grid else ''} ({context!r}; run {a.run}):",
              flush=True)
    if left:
        print(f"  left out: {', '.join(t['label'] for t in left)}: {a.mode} mode does not offer them "
              f"({paths.shown(Path(a.map))})", flush=True)
    if a.zone_grid:
        print("  zone grid sweep: " + sweep_words(), flush=True)
        if a.grip in TURNED:
            print(f"  held {held_words(a.grip)}, {VH_ROW} = {VH_OPTION[a.grip]}: each registration writes the records "
                  f"every orientation writes and {held_words(a.grip)}'s copies, which the proof lines cover; a place that "
                  "does not read as routed ends the walk with what the keys did, and the zone is put back and checked",
                  flush=True)
    for t in todo:
        r = afreg_run.route(t["label"], labels, axes) if labels else None
        way = (f"carousel {labels[r[0]]!r}" + (f", axis {axes[r[1]]['values'][r[2]]!r}" if r[1] else "")) if r \
            else f"no route in {paths.shown(Path(a.map)) if a.map else MAP_WORDS} and the axis walk"
        print(f"  {t['label']} (code {t['code']}): {way}; " + ("its edges" if a.edges else
              f"moved {say_moves(t['moves'])}, put back {say_moves(back_of(t['moves']))}"), flush=True)
    sets = [afreg_run.step_name(k, w) for k, w in setup_steps(focus, drive, amt, a.grip,
                                                               a.edges or (a.zone_grid and a.grip in TURNED), a.vh)]
    print(f"set through the menu first: {'; '.join(sets)}; the start file put back at the end puts them back",
          flush=True)
    for said in mode_said(a):
        print(said, flush=True)
    if amt:
        print(f"the download after the setup must hold {amt}'s code {want[1]} in {want[0]} ({AMT_ROW}, as the "
              "definition codes it), or the run stops before any area", flush=True)
    if stops:
        print(f"the download after the setup must hold {CIRC_OFF}'s code {stops[1]} in {stops[0]} ({CIRC_ROW}, as the "
              "definition codes it), or the run stops before any area: a frame that wraps round has no edge", flush=True)
    if amt and not a.grip and not a.edges:  # with a grip no delta is judged against the presses' directions
        print(f"the step per press is to be read from the deltas of the point and box areas (Spot, Expand Spot, Custom): "
              f"{step_words(moves or MOVES)} (a Zone moves one press each way over its 3 x 3 grid: no step)", flush=True)
    if afreg_run.vertical_plan(a.grip, {s["key"]: s for s in doc.get("settings") or []}):
        print(afreg_run.vertical_plan(a.grip, {s["key"]: s for s in doc.get("settings") or []}), flush=True)
    if a.edges:
        per, total = edge_minutes(a.edge_presses, len(todo))
        print(f"each area, {a.edge_presses} presses a push: slot 1 registered ({MEMORY_ROW}) at its start; pushed Left "
              "and Up to the low corner; one press Right, then Right and Down, then Down, each read once it settles "
              "(Right alone tells what Right moves, the second press off the edge its step); pushed Right, then Down, "
              "to the far corner; each registered and downloaded; brought back by presses computed from the far corner "
              f"and registered once more, which must match the first: {len(EDGE_TAGS) + 1} registrations an area, up "
              f"to {EDGE_TRIES} more to make good a press the camera lost; the zones are left out, their places the "
              "nine --zone-grid proves", flush=True)
        print(f"about {per} minutes an area ({REG_S} s a registration, {PUSHED_S} s a pushed press, not yet timed on "
              f"the camera), {total} minutes for these {len(todo)}", flush=True)
        if amt == "Large":
            print(f"under Large each way back is made under Standard: {AMT_ROW} = Standard through its row once the far "
                  "corner is registered, the presses counted in Standard's step (the hand tables' FRAME_STEPS), and "
                  "Large again before the next area, whose start must read Large", flush=True)
    slot, keys = slot_words(doc, a.mode, a.memory_set)
    print(f"each area: slot 1 registered ({MEMORY_ROW}{'' if a.mode == 'Stills' else f'; in {a.mode} mode {slot}'}) "
          + ("at each step above" if a.edges else "before and after the moves"
             + (", and after the put-back, to check it" if a.check_back else ""))
          + f"; registering writes {keys}, which no settings file sets back: the restore check names "
            f"them and leaves them out; {slot} must be filled in the start file already", flush=True)
    if moves and not a.check_back:
        print("--moves with --no-check-back: without the check-back nothing tells whether the moves kept the frame clear "
              "of the limit of its travel", flush=True)
    if a.list or not (todo or a.zone_grid):
        return 0
    if not memory_allowed(a.allow):
        sys.exit(f"registering slot 1 opens {MEMORY_ROW}, a never-open action row (camkit.safety): it is opened only "
                 f"with the owner's word, --allow {MEMORY_ROW!r}")
    others = [x for x in a.allow if not memory_allowed([x])]
    if others:
        sys.exit(f"framepos_run: --allow names {others}: this run opens no never-open row but {MEMORY_ROW}")
    allowance = allowed_or_exit(a.allow)
    return prove(a, doc, todo, focus, drive, context, allowance, amt=amt)


if __name__ == "__main__":
    sys.exit(main())
