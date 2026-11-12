"""Find where each movable Focus Area keeps its frame's place: the area chosen, Stills slot 1 registered, the frame
moved with the multi-selector on the shooting screen, slot 1 registered again, the two downloads diffed (2026-11-09).

    .venv/bin/python -u kit/provers/framepos_run.py --list
    .venv/bin/python -u kit/provers/framepos_run.py --allow "Camera Set. Memory" [--areas "Zone,Spot: S"] [--limit N]
    .venv/bin/python -u kit/provers/framepos_run.py --allow "Camera Set. Memory" --areas "Custom 1" --moves "Right 1"
    .venv/bin/python -u kit/provers/framepos_run.py --summary            (the run's lines, deltas only; no camera)
    .venv/bin/python -u kit/provers/framepos_run.py --zone-grid --allow "Camera Set. Memory"     (the sweep only)

The camera (the a1 II, firmware 4.00): moving a focus frame on the shooting screen changes no live record; registering
a memory slot copies its place into that slot's memory set (kit/writer/a1_tables.py, ZONE and AF_NOTE: the Zone's
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
registration writes the three orientations' copies alike), and, when the plan holds a Tracking area, Mode Dial Control
Set's Drive Mode Dial = Set with Menu, Drive Mode = Single Shooting, its Focus Mode Dial = Set with Menu and Focus Mode
= Continuous AF (--drive-mode and --focus-mode as afreg_run has them). --frame-move-amt Standard or Large sets AF
Frame Move Amt (how far one press moves a frame) to that option by the menu with these rows, before any move, and the
context names it, so the step a press takes can be read from the deltas; the download after the setup must hold the
code the definition gives that option in AF Frame Move Amt's record (amt_code), or the run stops before any area
(the restore puts the setup back); leave (the default) keeps the camera's own. Then per area:
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
is printed (decision 16): each changed key with its delta, and the count of records that differ at the end.

--zone-grid (2026-11-09): with Switch V/H AF Area = Off one Zone move writes the zone's grid index into every copy at
once (set1:0x019a, the level memories, the six vertical copies), so a sweep of the nine places proves the vertical
copies' nine values without turning the camera. After the same setup, Zone chosen, slot 1 is registered and downloaded
(zone-start) and the start place read from set1:0x019a; the frame is led to the upper left by exact presses (Left
column+1 times, Up row+1 times: none goes past an edge, so the route holds whether the zone stops at an edge or wraps;
kit2_frame's notes do not say which), then Right, Right, Down, Left, Left, Down, Right, Right, slot 1 registered and a
download (zone-<place name>) at each, the place read from the download and checked against the route (a place that
reads otherwise stops the sweep); the frame put back where it started and registered once more (zone-back), which must
match zone-start. One line a place in zone_grid.jsonl: {"place" (code), "name", "expected", "confirmed", "download",
"records" (every set1 record that changed to the code), "groups" (horizontal, vertical A, vertical B)}; one proof line
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
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parent))
import afreg_run  # noqa: E402
from afreg_run import bare, slug  # noqa: E402
from camkit import definitions, jsonl, match, paths, safety  # noqa: E402
from runner import LATEST_SCAN, add_allow_argument, add_scan_argument, allowed_or_exit, read_json  # noqa: E402
from writer.a1_tables import ZONE  # noqa: E402

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
GROUPS = ("horizontal", "vertical A", "vertical B")


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


def setup_steps(focus: bool, drive: bool, amt: str | None = None) -> list:
    """[(kind, text)] the setup in order, as afreg_run.setup_steps names them: "dial" (a Mode Dial Control Set cell put
    on Set with Menu), "drive" (Drive Mode = Single Shooting), "row" (a list row: "path = option"); AF Frame Move Amt
    last, when amt names its option."""
    steps = [("dial", afreg_run.DRIVE_DIAL), ("drive", f"{afreg_run.DRIVE_ROW} = {afreg_run.SINGLE}")] if drive else []
    if focus:
        steps += [("dial", afreg_run.FOCUS_DIAL), ("row", f"{afreg_run.FOCUS_ROW} = {afreg_run.CONTINUOUS}")]
    return steps + [("row", f"{VH_ROW} = {OFF}")] + ([("row", f"{AMT_ROW} = {amt}")] if amt else [])


def setup_rows(amt: str | None = None) -> dict:
    """{a "row" step's text, as setup_steps names it: (the row's menu path, the option)}, AF Frame Move Amt's when amt
    names its option."""
    rows = {f"{afreg_run.FOCUS_ROW} = {afreg_run.CONTINUOUS}": ([afreg_run.FOCUS_ROW], afreg_run.CONTINUOUS),
            f"{VH_ROW} = {OFF}": ([VH_ROW], OFF)}
    return rows | ({f"{AMT_ROW} = {amt}": ([AMT_ROW], amt)} if amt else {})


def setting_code(index: dict, path: list, option: str) -> tuple | None:
    """(key, code): the live record a menu row writes, in the definition (`index`: its settings by key), and the code
    its values give `option`; None rather than a guess. The record is the one global setting with a proof of the row
    itself, made in no state the run cannot vouch for: the row's path with no suffix, or with "[by hand]", which says
    how the proof was made, not a state ("Viewfinder Bright. > Brightness Setup [by hand]"); a proof only "[Movie mode]"
    or under any other state names no record here, and neither does a setting's name alone. The option's code: the one
    label written exactly as the option is given; with none, the one label camkit.match.index_of names, the kit's rule
    for naming an option from a reading (match.norm, which keeps a decimal point between digits and compares digits
    exactly: "F1.1" is not "F11", 2.5" not 25"; else the only label match.same takes). None when no label, or more than
    one, is named at the step that decides: never the first of several."""
    row = " > ".join(path)

    def vouched(menu: str) -> bool:
        m = re.fullmatch(r"(.*?)(?: \[([^\]]*)\])?", menu)
        return m.group(1) == row and m.group(2) in (None, "by hand")
    hits = [s for k, s in index.items() if k.startswith("global:")
            and any(vouched(m) for m in (s.get("proved") or {}).get("menu") or [])]
    if len(hits) != 1:
        return None
    values = [(v, lab) for v, lab in hits[0].get("values") or []]
    exact = [i for i, (_, lab) in enumerate(values) if str(lab).strip() == str(option).strip()]
    i = (exact[0] if len(exact) == 1 else None) if exact else match.index_of([lab for _, lab in values], option)
    return None if i is None else (hits[0]["key"], values[i][0])


def amt_code(index: dict, amt: str) -> tuple | None:
    """(key, code): AF Frame Move Amt's live record in the definition and the code its values give the option `amt`
    (setting_code: the a1 II's global:0x03a3, Standard 0 and Large 1, proved by the menu in pass 2, kit2_pass2); None
    when the definition has no such record, or its values do not name the option."""
    return setting_code(index, [AMT_ROW], amt)


def context_of(extra: str | None, amt: str | None = None, moves: list | None = None) -> str:
    """The state the registrations are made in, which every line carries and the summary keeps apart: AF Frame Move Amt
    when the run sets it, the moves when --moves gave them ("moved Right 1"), then --context."""
    base = (f"{VH_ROW} {OFF}, camera level" + (f", {AMT_ROW} {amt}" if amt else "")
            + (f", moved {say_moves(moves)}" if moves else ""))
    return f"{base}, {extra}" if extra else base


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


def verdict(items: list, done: list) -> str:
    if not any(n for _, n in done):
        return ("no press was taken (each refused or answered by a notice)"
                + (f"; yet {len(items)} records changed" if items else ": nothing to judge"))
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
              back_changes: list | None = None) -> dict:
    """The area's line for framepos.jsonl: the changes as the diff gives them (before and after: the run's own evidence,
    kept in runs/ alone), how each is judged and the verdict; "back" says whether the registration after the put-back
    matched the first (None without --check-back)."""
    items = judged(changes, index, done)
    line = {"t": round(time.time(), 3), "area": t["label"], "code": t["code"], "moves": t["moves"], "sent": sent,
            "taken": done, "put_back": put_back, "changed": changes, "judged": items, "verdict": verdict(items, done),
            "frames": frames, "files": files}
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


def summary_of(line: dict) -> list:
    """The area's lines of the summary: what moved, by key and delta only (never a value a record held)."""
    head = f"{line['area']} (code {line.get('code')}" + (f"; {line['context']})" if line.get("context") else ")")
    if line.get("failed"):
        return [f"{head}: failed: {line['failed']}"]
    out = [f"{head}, {say_moves(line['moves'])} asked, {say_moves(line.get('taken') or [])} taken: {line['verdict']}"]
    for i in line.get("judged") or []:
        mark = "  [the other way]" if i["with_presses"] is False else ""
        out.append(f"    {i['key']}  {i['name'] or '(not in the definition)'}: {said_delta(i)}{mark}")
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


def slot_filled(cs) -> bool:
    """Slot 1 registered already in a settings file (its filled mark, FILLED): registering an empty one would mark it
    filled for good, since no settings file empties it."""
    from prove_run import held_value
    key, code = FILLED
    return held_value(cs, key) == code


# ---------------------------------------------------------------- the zone grid sweep (no camera)

def zone_names(table=ZONE) -> dict:
    """{code: name} of the Zone grid table (kit/writer/a1_tables.py ZONE)."""
    return {int(c): n for c, n in table}


def code_place(code, table=ZONE) -> tuple | None:
    """A grid code's place (column, row), left and up negative, or None for a code the table does not name."""
    return place_of(zone_names(table).get(code))


def place_name(place: tuple, table=ZONE) -> str | None:
    """The table's name for a place (column, row), or None."""
    for _, n in table:
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
    """The orientation group of a zone record by the definition's name: vertical A, vertical B, else horizontal (the
    current record and the level memories)."""
    n = name or ""
    return "vertical A" if "vertical A" in n else "vertical B" if "vertical B" in n else "horizontal"


def holders(changes: list, code) -> list:
    """The set1 records that changed to `code` between two downloads (keys; a record of several values is left out)."""
    return [c["key"] for c in changes if c["key"].startswith("set1:") and not isinstance(c["after"], list)
            and c["after"] == code]


def groups_of(keys: list, index: dict) -> dict:
    """{group: [keys]} of the records, by the definition's names (def_key); the three groups always present."""
    out = {g: [] for g in GROUPS}
    for k in keys:
        out[zone_group((index.get(def_key(k)) or {}).get("name"))].append(k)
    return out


def zone_records(index: dict) -> list:
    """The zone grid records the sweep proves, as definition keys ("set:0x0f32"): the six vertical copies and the
    current record, found by their names in the definition."""
    return sorted(k for k, s in index.items() if k.startswith("set:") and "Zone position" in (s.get("name") or "")
                  and "grid index" in s["name"] and ("vertical" in s["name"] or "(current" in s["name"]))


def sweep_line(k: int, expected: tuple, code, base_changes: list, download: str, index: dict, table=ZONE) -> dict:
    """The place's line for zone_grid.jsonl: {"place" (the code read from the download), "name" (the table's), "expected"
    (the place the route led to), "confirmed", "download", "records" (every set1 record that changed to the code),
    "groups"}; no value but the codes."""
    name = zone_names(table).get(code)
    keys = holders(base_changes, code)
    return {"t": round(time.time(), 3), "n": k + 1, "place": code, "name": name, "expected": place_name(expected, table),
            "confirmed": name is not None and code_place(code, table) == tuple(expected), "download": download,
            "records": keys, "groups": groups_of(keys, index)}


def sweep_proofs(line: dict, held: dict, base: str, changes: list, index: dict, tag: dict) -> list:
    """One proof line per zone record (zone_records) for the place: applied only when the place reads as the route led
    (line["confirmed"]), the record holds the place's code and it changed to it from the download before (it is among
    line["records"]). An unconfirmed place's download may still hold the start place, and a record that holds the code
    without changing may hold what the camera had, so neither is credited: a put-back by another name (decision 16).
    `held`: {definition key: value in the place's download}; `changes`: the diff from the previous download."""
    code, out = line["place"], []
    for rec in zone_records(index):
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
                    "via": f"Focus Area = Zone with {VH_ROW} = {OFF}, the frame moved with the multi-selector to the "
                           f"{line['name']} place, then slot 1 registered ({MEMORY_ROW}, Enter on the slot)",
                    "slot": "1", "base": base, "dat": line["download"], "after": line["download"], "changes": ch,
                    "applied": applied, **({} if applied else {"not_applied": why}), **tag})
    return out


def place_written(run_dir: Path, line: dict, held: dict, base: str, changes: list, index: dict, tag: dict) -> list:
    """A place of the sweep written: its line in zone_grid.jsonl always (confirmed or not), and its proof lines
    (sweep_proofs) in proofs.jsonl, the run marked as a proof run, only once the place reads as the route led
    (line["confirmed"]): an unconfirmed place writes no proof line. Returns the proof lines written."""
    from camkit.runs import mark_proof_run
    jsonl.append(run_dir / "zone_grid.jsonl", dict(line, **tag))
    if not line.get("confirmed"):
        return []
    got = sweep_proofs(line, held, base, changes, index, tag)
    for p in got:
        jsonl.append(run_dir / "proofs.jsonl", p)
    mark_proof_run(run_dir, "kit/provers/framepos_run.py --zone-grid")     # the writer reads these lines
    return got


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
    why, _ = drive.press_decision(f"enter!:{SLOT_SCREEN.pattern}", "enter", lit, t, cam.read().kind, False, allow)
    if why:
        raise Failed(f"{MEMORY_ROW}: Enter refused on the slot screen ({cam.frame.path.name}): {why}")
    slots = cam.frame.path.name
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


def press_moves(cam, moves: list, sent: list, done: list) -> None:
    """The multi-selector's presses on the shooting screen, each named for it (on_shooting: the link sends no key but
    MENU there unnamed, decision 21) and each read, filling `sent` ({"key", "frame", "screen"}, and
    "refused" or "notice" when so) and `done` ([key, presses taken], one per move) as they go, so a caller whose area
    fails knows what was taken. A press the link refuses, or one a notice answers (waited out, NOTICE_S), is recorded
    and not counted; a screen that is not the shooting screen before a press, or a notice that stays, fails the area."""
    from camkit.link import LinkError
    from camkit.live import text_of
    from prove_run import Failed
    for key, n in moves:
        done.append([key, 0])
        for _ in range(n):
            if cam.read().kind != "shooting":
                raise Failed(f"not on the shooting screen before {WORDS[key]} ({cam.read().kind}, {cam.frame.path.name})")
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
            rec["notice"] = " ".join(text_of(cam).split())[:200]
            if not back_to_shooting(cam):
                cam.run.log("shooting_screen_left", step=WORDS[key], frame=rec["frame"], notice=rec["notice"])
                raise Failed(f"{WORDS[key]} left the shooting screen ({rec['screen']}, {rec['frame']}; what it showed is "
                             "in the run's events.jsonl)")


def prepare(cam, link, hdmi, run, cycle, model, focus: bool, drive: bool, start: Path, amt: str | None = None,
            index: dict | None = None) -> list:
    """The setup through the menu (setup_steps, each as afreg_run.prepare takes it), then a download kept in setup.jsonl
    with the keys it changed; returns the steps. The count only is printed. With amt, the download must hold the code
    the definition (`index`, its settings by key) gives that option in AF Frame Move Amt's record (amt_code): a menu
    that did not take it fails the run before any area, the value found never said (the restore puts the setup back)."""
    from camkit import camset
    from mode_switch import open_menu
    from prove_run import LOCK_S, Failed, held_value, to_shooting
    from runner import close_screen
    want = amt_code(index or {}, amt) if amt else None
    if amt and want is None:
        raise Failed(f"the definition gives no code for {AMT_ROW} = {amt}: the run could not tell whether the camera "
                     "took it")
    rows = setup_rows(amt)
    steps = []
    for kind, what in setup_steps(focus, drive, amt):
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
    jsonl.append(run.dir / "setup.jsonl", {"t": round(time.time(), 3), "steps": steps, "start": start.name,
                                           "after": ref.name, "changed": changed,
                                           **({"frame_move_amt": {"asked": amt, "took": took}} if amt else {})})
    print(f"setup: {'; '.join(steps)}; {len(changed)} records now differ from the start file (the restore puts them "
          "back)", flush=True)
    if amt and not took:
        raise Failed(f"{AMT_ROW} did not take {amt} through the menu; the setup is undone by the restore")
    time.sleep(LOCK_S)
    return steps


def one_area(cam, link, hdmi, run, cycle, model, labels, axes, t: dict, r: tuple, a, index: dict, owed: list) -> dict:
    """One area: chosen, slot 1 registered, a download; the frame moved, registered, a download; the diff; the frame put
    back (and, with --check-back, registered and downloaded once more). `owed` holds the presses that would put the
    frame back while it is moved, for the caller to send if the area fails. Returns the area's line."""
    from camkit import camset
    from prove_run import to_shooting
    from runner import changes_of
    got = afreg_run.choose_area(cam, run, cycle, model, labels, axes, r, None)
    to_shooting(link, hdmi, "the shooting screen with the area chosen")
    frames = {"chosen": got["chosen_frame"], "after_ok": got["row_frame"]}
    frames["base_registration"] = register_slot(cam, cycle, model, a.allow)["frames"]
    base, at = download(cam, link, hdmi, f"base-{slug(t['label'])}")
    afreg_run.ready_to_hold(cam, at)                    # the download's message gone, the menu lock passed
    sent, done = [], []
    try:
        press_moves(cam, t["moves"], sent, done)
    finally:
        owed[:] = back_of(done)
    frames["moves"] = [x["frame"] for x in sent if x.get("frame")]
    frames["moved_registration"] = register_slot(cam, cycle, model, a.allow)["frames"]
    moved, at = download(cam, link, hdmi, f"moved-{slug(t['label'])}")
    changes = changes_of(camset.diff(camset.read(base), camset.read(moved)))
    afreg_run.ready_to_hold(cam, at)
    back, back_sent, back_done = list(owed), [], []
    try:
        press_moves(cam, back, back_sent, back_done)
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
        afreg_run.ready_to_hold(cam, at)                # the menu lock passed before the next area's MENU
    line = area_line(t, changes, index, sent + [dict(x, put_back=True) for x in back_sent], done, back_done, frames,
                     files, back_changes)
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
    presses that put the frame back at the start, kept current for the caller. Returns the sweep's summary line."""
    from camkit import camset
    from prove_run import Failed, held_value, to_shooting
    from runner import changes_of
    got = afreg_run.choose_area(cam, run, cycle, model, labels, axes, r, None)
    to_shooting(link, hdmi, "the shooting screen with Zone chosen")
    register_slot(cam, cycle, model, a.allow)
    start, at = download(cam, link, hdmi, "zone-start")
    afreg_run.ready_to_hold(cam, at)
    cs0 = camset.read(start)
    code0 = held_value(cs0, ZONE_CURRENT)
    place0 = code_place(code0)
    if place0 is None:
        raise Failed(f"the start download holds no zone place the table names ({ZONE_CURRENT}, {start.name})")
    # the start place is the owner's: read from the download and kept there, never printed (decision 16)
    print(f"  zone sweep: the start place was read from the download ({start.name})", flush=True)
    done, sent, rows = [], [], []

    def go(moves):
        try:
            press_moves(cam, moves, sent, done)
        finally:
            owed[:] = net_back(done)
    go(corner_moves(place0))
    prev_cs, prev_name = cs0, start.name
    for k, (step, expected) in enumerate(sweep_route()):
        if step:
            go([[step, 1]])
        want = place_name(expected)
        register_slot(cam, cycle, model, a.allow)
        dat, at = download(cam, link, hdmi, f"zone-{slug(want)}")
        afreg_run.ready_to_hold(cam, at)
        cs = camset.read(dat)
        code = held_value(cs, ZONE_CURRENT)
        changes = changes_of(camset.diff(prev_cs, cs))
        line = sweep_line(k, expected, code, changes, dat.name, index)
        held = {rec: held_value(cs, rec.replace("set:", "set1:", 1)) for rec in zone_records(index)}
        place_written(run.dir, line, held, prev_name, changes, index, tag)     # proof lines once confirmed only
        rows.append(line)
        if not line["confirmed"]:
            # what an unconfirmed place's download holds may be the start place, the owner's: in zone_grid.jsonl only
            print(f"  zone sweep {k + 1}/9: {want} NOT as routed (what the download holds is in zone_grid.jsonl)",
                  flush=True)
            raise Failed(f"the zone sweep's place {k + 1} does not read as {want}: the route does not hold ({dat.name})")
        print(f"  zone sweep {k + 1}/9: {want} -> code {code} ({line['name']}), confirmed; records: "
              f"{', '.join(line['records']) or 'none'}", flush=True)
        prev_cs, prev_name = cs, dat.name
    back = net_back(done)
    go(back)
    register_slot(cam, cycle, model, a.allow)
    again, at = download(cam, link, hdmi, "zone-back")
    afreg_run.ready_to_hold(cam, at)
    off = changes_of(camset.diff(cs0, camset.read(again)))
    # the presses that put it back tell where it started: in the sweep's line only, never printed
    print("  zone sweep: put back where it started; the registration after it "
          + ("matched the start's" if not off else f"differs from the start's in {', '.join(c['key'] for c in off)}"),
          flush=True)
    return {"t": round(time.time(), 3), "sweep": "zone-grid", "places": len(rows),
            "confirmed": sum(x["confirmed"] for x in rows), "put_back": back, "back_same": not off,
            "back_off": [c["key"] for c in off], "files": {"start": start.name, "back": again.name},
            "frames": {"chosen": got["chosen_frame"]}, **tag}


def prove(a, doc: dict, todo: list, focus: bool, drive: bool, context: str, allowance: str, amt: str | None = None) -> int:
    from camkit.frames import eyes_from_config
    from camkit.runs import Run
    from mode_switch import MAY_OPEN
    from pass3_run import labels_of
    from prove_run import AXES
    from runner import load_scan, prover_session, write_text
    labels, kind = labels_of([ROW])
    if kind != "dialog":
        sys.exit(f"{ROW} is a {kind} in pass 1's map, not a carousel")
    axes = {o: info for o, info in read_json(AXES).get(ROW, {}).items() if len(info["values"]) > 1}
    routes = {t["label"]: afreg_run.route(t["label"], labels, axes) for t in todo + ([a.zone_target] if a.zone_grid else [])}
    lost = [lab for lab, r in routes.items() if r is None]
    if lost:
        sys.exit(f"pass 1's map and the axis walk ({AXES}) do not name {lost} once: walk the axes first "
                 "(kit/axis_walk.py --rows 'Focus Area')")
    index = {s["key"]: s for s in doc.get("settings") or []}
    cycle, model = load_scan(a.scan)
    run = Run(a.run)
    hdmi = eyes_from_config(run)
    out = run.dir / "framepos.jsonl"
    tag = {"context": context, **({"allowance": allowance} if allowance else {})}
    # a zone moves by its own one-step moves (the sweep by its route), never by --moves: its lines carry the context a
    # run without --moves gives, so they match a default run's
    zone_tag = dict(tag, context=context_of(a.context, amt))
    lines = []
    may_open = set(a.allow) | (set(MAY_OPEN) if focus or drive else set())
    try:
        with prover_session(run, hdmi, may_open=may_open, show=0, expected=frozenset(EXPECTED_LEFT),
                            end_why="the settings download after the frames") as s:
            areas(s, a, run, hdmi, cycle, model, labels, axes, todo, routes, index, focus, drive, out, tag, lines, amt,
                  zone_tag)
    finally:
        if out.exists():
            summary = summary_lines(jsonl.read(out))
            write_text(run.dir / "framepos_summary.txt", "\n".join(summary) + "\n")
        found = sum(1 for ln in lines if ln.get("changed"))
        if todo:
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
    each area's line written and summed up as it comes; three areas failing in a row end it. A zone's line, and the
    sweep's, carry `zone_tag` (the context without --moves, which a zone never takes) in place of `tag`."""
    zone_tag = zone_tag or tag
    from camkit import camset
    from prove_run import Failed
    from runner import close_screen
    cam, link = s.cam, s.link
    if not slot_filled(camset.read(s.start)):
        raise Failed("slot 1 is empty in the start file: registering it would mark it filled for good (no settings "
                     "file empties it); this run registers a filled slot only")
    setup = prepare(cam, link, hdmi, run, cycle, model, focus, drive, s.start, amt, index)
    if a.zone_grid:
        zone_grid(s, a, run, hdmi, cycle, model, labels, axes, routes, index, out, zone_tag, lines, setup)
    in_a_row = 0
    for t in todo:
        owed = []
        try:
            line = one_area(cam, link, hdmi, run, cycle, model, labels, axes, t, routes[t["label"]], a, index, owed)
            in_a_row = 0
        except Failed as e:
            print(f"  {t['label']}: {e}", flush=True)
            close_screen(cam, link)
            line = {"t": round(time.time(), 3), "area": t["label"], "code": t["code"], "failed": str(e)}
            if owed:                                # the frame is moved: put it back before the next area
                sent, done = [], []
                try:
                    press_moves(cam, owed, sent, done)
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
                press_moves(cam, owed, sent, done)
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


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--areas", default=None,
                    help="default (the fourteen movable areas of DEFAULT_AREAS; what runs when neither this nor "
                         "--zone-grid is given), all, or the definition's labels, comma-separated ('Zone,Spot: S')")
    ap.add_argument("--zone-grid", action="store_true",
                    help="sweep the Zone's nine grid places, slot 1 registered at each (zone_grid.jsonl); alone it runs "
                         "this sweep only, with --areas the sweep first, then those areas")
    add_allow_argument(ap)
    ap.add_argument("--focus-mode", choices=("auto", "menu", "leave"), default="auto",
                    help="auto: Focus Mode = Continuous AF through the menu (its dial set with the menu) when the plan "
                         "holds a Tracking area; menu: always; leave: as the camera has it")
    ap.add_argument("--drive-mode", choices=("auto", "menu", "leave"), default="auto",
                    help="auto: Drive Mode Dial = Set with Menu and Drive Mode = Single Shooting when the plan holds a "
                         "Tracking area (the camera refuses Continuous AF under some drive modes); menu: always; "
                         "leave: as it is")
    ap.add_argument("--frame-move-amt", choices=("Standard", "Large", "leave"), default="leave",
                    help="Standard or Large: AF Frame Move Amt put on it through the menu with the other setup rows, so "
                         "the step a press moves the frame can be measured under it; leave: as the camera has it "
                         "(default)")
    ap.add_argument("--moves", default=None,
                    help="the presses that move a point or box area's frame in place of Left 3, Up 2: a direction (Left, "
                         "Right, Up, Down) and one to nine presses, comma-separated in the order taken ('Right 1', "
                         "'Left 1,Up 1'); a direction once, never with its opposite. For a frame near the limit of its "
                         "travel; Zone and Tracking: Zone keep their one-step moves")
    ap.add_argument("--check-back", action=argparse.BooleanOptionalAction, default=True,
                    help="register slot 1 once more after the frame is put back and check it matches the first "
                         "(default; --no-check-back skips it)")
    add_scan_argument(ap, default=LATEST_SCAN, mode="Stills")
    ap.add_argument("--run", default="kit2_framepos")
    ap.add_argument("--context", default=None, help="more of the state these registrations are made in")
    ap.add_argument("--limit", type=int, default=0, help="the first N areas of the plan only")
    ap.add_argument("--list", action="store_true", help="print the plan only; no camera")
    ap.add_argument("--summary", action="store_true", help="print what the run's lines found, deltas only; no camera")
    a = ap.parse_args(argv)
    if a.summary:
        got = summary_lines(jsonl.read(paths.run_root() / a.run / "framepos.jsonl"))
        print("\n".join(got) if got else "no line in the run")
        return 0
    moves = parse_moves(a.moves) if a.moves is not None else None
    doc = definitions.with_evidence(read_json(definitions.active()), definitions.active())
    todo = plan(doc, a.areas or "default", moves) if a.areas or not a.zone_grid else []
    a.zone_target = plan(doc, "Zone")[0] if a.zone_grid else None
    if a.limit:
        todo = todo[:a.limit]
    if moves and all(gridded(t["label"]) for t in todo):
        sys.exit(f"framepos_run: --moves {a.moves!r}: no area of the plan takes them (Zone and Tracking: Zone keep their "
                 "one-step moves, --zone-grid its route)")
    tracking = any(t["tracking"] for t in todo)
    focus = a.focus_mode == "menu" or (a.focus_mode == "auto" and tracking)
    drive = a.drive_mode == "menu" or (a.drive_mode == "auto" and tracking)
    amt = None if a.frame_move_amt == "leave" else a.frame_move_amt
    want = amt_code({s["key"]: s for s in doc.get("settings") or []}, amt) if amt else None
    if amt and want is None:
        sys.exit(f"framepos_run: --frame-move-amt {amt}: the definition has no {AMT_ROW} record whose values name "
                 f"{amt!r}, so the run could not check that the camera took it")
    context = context_of(a.context, amt, moves)
    print(f"{len(todo)} areas{' and the zone grid sweep' if a.zone_grid else ''} ({context!r}; run {a.run}):", flush=True)
    try:
        from pass3_run import labels_of
        from prove_run import AXES
        labels, _ = labels_of([ROW])
        axes = {o: info for o, info in read_json(AXES).get(ROW, {}).items() if len(info["values"]) > 1}
    except (SystemExit, OSError, ValueError):
        labels, axes = None, None
    if a.zone_grid:
        print("  zone grid sweep: " + sweep_words(), flush=True)
    for t in todo:
        r = afreg_run.route(t["label"], labels, axes) if labels else None
        way = (f"carousel {labels[r[0]]!r}" + (f", axis {axes[r[1]]['values'][r[2]]!r}" if r[1] else "")) if r \
            else "no route in pass 1's map and the axis walk"
        print(f"  {t['label']} (code {t['code']}): {way}; moved {say_moves(t['moves'])}, put back "
              f"{say_moves(back_of(t['moves']))}", flush=True)
    sets = [afreg_run.step_name(k, w) for k, w in setup_steps(focus, drive, amt)]
    print(f"set through the menu first: {'; '.join(sets)}; the start file put back at the end puts them back",
          flush=True)
    if amt:
        print(f"the download after the setup must hold {amt}'s code {want[1]} in {want[0]} ({AMT_ROW}, as the "
              "definition codes it), or the run stops before any area", flush=True)
        print(f"the step per press is to be read from the deltas of the point and box areas (Spot, Expand Spot, Custom): "
              f"{step_words(moves or MOVES)} (a Zone moves one press each way over its 3 x 3 grid: no step)", flush=True)
    print(f"each area: slot 1 registered ({MEMORY_ROW}) before and after the moves"
          + (", and after the put-back, to check it" if a.check_back else "")
          + f"; registering writes {', '.join(EXPECTED_LEFT)}, which no settings file sets back: the restore check names "
            "them and leaves them out; slot 1 must be filled in the start file already", flush=True)
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
