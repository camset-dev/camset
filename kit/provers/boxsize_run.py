"""Measure what a Custom focus box's size allows: resized in its editor by the dials, each size kept and registered, the
smallest and largest width and height and the pattern of the dials' steps read from the registrations, and the box's
travel limits measured at chosen sizes against the rule (2026-11-17).

    .venv/bin/python -u kit/provers/boxsize_run.py --box "Custom 1" --list
    .venv/bin/python -u kit/provers/boxsize_run.py --allow "Camera Set. Memory" --allow "Focus Area's SET" --box "Custom 1" --probe rear_l
    .venv/bin/python -u kit/provers/boxsize_run.py --allow "Camera Set. Memory" --allow "Focus Area's SET" --allow "Custom box Reset" --box "Custom 1"
    .venv/bin/python -u kit/provers/boxsize_run.py --allow "Camera Set. Memory" --allow "Focus Area's SET" --allow "Custom box Reset" --put-back RUN

The camera (the a1 II; runs/<model>_fw<fw>/kit2_freesize, 2026-11-02, by kit/drive.py; kit2_boxsize_c1_probe_w3,
_probe_h3 and _width, 2026-11-17): on Focus Area's chooser with a Custom box lit, the trash button reads SET, and SET
(C4) opens the box's size editor, a screen of no known kind: its title ("Custom 1"), the box drawn in orange, the three
dials' icons, its footer Reset (the trash button), MENU Cancel and OK. There the front dial sets the height, 12 a click,
and the rear dial L the width, 16 a click, from 28 to 548 for Custom 1; each click steps from the size the box has and
stops at an end, so Sony's default (402) lies on neither end's ladder. One dial command moves one click, whatever its
steps ("dial rear_l -10" moved 16): each click is its own command (turn). Reset puts the box back to its default size,
both dimensions, the editor left open on it (kit2_freesize 00563 -> 00564; the registration after it moved the size
records alone); OK keeps the size and leaves for the shooting screen, MENU cancels it. The sizes (the hand tables'
FRAME_TRAVEL "Custom" boxes:
Custom 1 set:0x14b6/0x14b4, Custom 2 0x14ba/0x14b8, Custom 3 0x14be/0x14bc, the box in use 0x148a/0x1488, the defaults
by the definition's names) reach the file only when a Camera Set. Memory slot is registered, as the places do, and a
file put back does not put a live box's size back: every size here is read from slot 1 registered after it
(framepos_run.register_slot, through framepos_run.Walk), and the run puts the size back itself.

A run is bracketed as every run is (decision 15; runner.prover_session): the start download (slot 1 must be filled in
it, and its Aspect Ratio one the rule has a picture for, else the run stops before its first press), the setup through
the menu as
framepos_run.py --edges has it (Switch V/H AF Area Off, the camera level; Circ. of Focus Point = Does Not Circulate; AF
Frame Move Amt = Standard), the box chosen and registered (the start: its size and place), then:
  --probe DIAL (the smallest try): --clicks single clicks up, each kept and registered, then as many down, each
    registered: the steps near the start size, and whether they come back to it exactly; nothing else.
  else, per dial of --dials (rear_l: the width, front: the height): turns of --block clicks toward its smallest, each
    followed by --confirm clicks more, until those change nothing (the end, said by value: a camera fact), the edges
    measured there, --pattern single clicks up from it (the steps); the same toward its largest and down from it; then
    back to the start by counted clicks (seek). Then one odd size (ODD: rear_l +7, front -5 clicks from the start), the
    edges measured there, and the turns undone. The edges are also measured at the start size first, so the place can be
    brought back at that size.
Each size is set the same way (Sizes.point_turns): MENU, Focus Area by the scan, Right, the box under the carousel's
cursor (afreg_run.choose_level), the chooser read as Focus Area's with that box lit and SET on its trash button
(chooser_refused), SET (C4, allowed on that dialog: camkit.safety's C4 rules), the editor read as that box's own
(editor_refused); each click of a dial its own command, each only once the screen read just before it is that editor
(turn: never the shooting screen, where a dial changes the live exposure, which the link refuses there besides); OK
with the camera's consent for that one press on that editor (camkit.live.BoxEditor: the editor reads as no
known kind and its footer's Reset is a confirmation's word, so no other way past answers it), the shooting screen; slot
1 registered and downloaded; the size and place read. A registration's place against the one before it says whether the
size moved the box (a finding, by delta). The editor's box, measured in orange on the frame before OK, is kept beside
each size ("screen_box", pixels): the registration is the judge.
The edges at a size are framepos_run.edge_area's (as --edges measures them, the frame brought back to where that measure
began), written to the run's edges.jsonl with the size, so framepos_run.py --put-back RUN can read them; each record of
the box's place is then judged against the rule (predicted: kit/writer/frames.box_limits on FRAME_TRAVEL's rule for
the box, rule_of, at the Aspect Ratio the start download holds): match, or each limit's difference.

The size put back: by counted clicks from the steps measured (seek), each landing kept and registered, never guessed;
where no click lands on the start (two sizes a click apart either side of it) or an end lies before it, by the editor's
Reset (reset_back) when the start size is the default records' and the run has the owner's word for it, --allow "Custom
box Reset" (the a1 II's owner, 2026-11-17: decision 7): the editor opened, C4 with the camera's consent for that press
on that editor (camkit.live.BoxReset, which hands the link the size editor kind decision 7 names), the
screen read again as that editor (a question or any other screen stops the run there, nothing answered), OK kept,
slot 1 registered, the size judged against the default records and the start's. Else, or where a Reset does not give
the defaults, the difference is said with what to do by hand. At the end slot 1 is registered once more and its size
and place judged against the start's; a place
off is brought back as --put-back brings a frame (framepos_run.put_back_area, from the edges measured at the start
size). A run that stops leaves what it says: --put-back RUN brings the box back to RUN's start size (its boxsize.jsonl's
start line), by clicks or by Reset as above, then its place (RUN's edges at the start size), each registered and
checked.

Lines in the run's boxsize.jsonl, each with the context (camera level, Switch V/H AF Area Off, AF Frame Move Amt, the
Aspect Ratio read from the start download): the start ("default": whether the start size is the defaults'), each size
("turns", "size", "place", "place_moved", "screen_box", "file"), each dial's ends ("what": "end") and steps ("what":
"pattern"), each travel ("what": "travel": the size, each record's measured and predicted limits) and the finish. The
data agent extends FRAME_TRAVEL's sizes_tried (or sizes_range, both ends and sizes between tried) and the size records'
ranges from them; no kit step writes them.

Nothing a record held is printed but sizes and limits, camera facts: a start size that is not the defaults' is the
owner's (decision 16), never printed; the sizes reached from it are said by their difference from it, and the limits at
it by match or difference alone. The ends and the steps from them are said by value.
Unknowns only the camera can settle, each a finding in the lines, never a crash: whether the three boxes share one size
range or step (a run a box); whether a size moves the box's place (place_moved); whether Tracking: Custom shares the
plain box's size (--tracking: at the odd size, Tracking: Custom chosen and registered, the box in use read beside the
box's own).
"""
import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parent))
import afreg_run  # noqa: E402
import framepos_run as F  # noqa: E402
from afreg_run import bare, slug  # noqa: E402
from camkit import definitions, jsonl, paths, safety  # noqa: E402
from runner import LATEST_SCAN, add_allow_argument, add_scan_argument, allowed_or_exit, read_json  # noqa: E402
from writer import frames, hand_tables  # noqa: E402

PROG = "kit/provers/boxsize_run.py"
BOXES = ("Custom 1", "Custom 2", "Custom 3")
DIALS = {"rear_l": "width", "front": "height"}          # the editor's dials and what each sets (kit2_freesize)
DIAL_WORDS = {"rear_l": "the rear dial L", "front": "the front dial"}
SET_WORD = "Focus Area's SET"                            # the owner's word for SET (drive.py's c4set), given per run
# the owner's word for the size editor's Reset, given per run as drive.py takes each C4 go-ahead apart (its c4set and
# c4reset): the a1 II's owner's of 2026-11-17 (decision 7)
RESET_WORD = "Custom box Reset"
BLOCK, CONFIRM, PATTERN = 40, 2, 6                       # a turn toward an end; the clicks that check it; single clicks
ENDS_TRIES, SEEK_TRIES = 8, 8                            # turns toward an end; landings on the way back
UNIT = {"rear_l": 16.0, "front": 12.0}                   # a click's size before one is measured (kit2_boxsize_c1_probe_*)
ODD = (("rear_l", 7), ("front", -5))                     # the odd size, in clicks from the start
PROBE_CLICKS = 3
OUT = "boxsize.jsonl"
# the size editor: its title, then its footer's Reset and Cancel (kit2_freesize: "Custom 1 iReset MENU Cancel OK"); it
# reads as no known kind
EDITOR_RE = r"^\W*custom\s*{n}\b[\s\S]*reset[\s\S]*cancel"
EDITOR_KINDS = ("unknown",)
# the band of the editor's frame the box is drawn in (above the dials' icons, below the title)
BOX_BAND = (50, 370)


# ---------------------------------------------------------------- the plan, the records and the rule (no camera)

def read_definition() -> dict:
    return definitions.with_evidence(read_json(definitions.active()), definitions.active())


def custom_table() -> dict:
    """The hand tables' FRAME_TRAVEL "Custom" entry of the camera the kit works on."""
    got = (hand_tables.active().FRAME_TRAVEL or {}).get("Custom")
    if not got:
        sys.exit("boxsize_run: the hand tables of the camera the kit works on hold no FRAME_TRAVEL \"Custom\" entry: "
                 "which records hold a box's size and place is not known")
    return got


def box_records(doc: dict, box: str, table: dict) -> dict:
    """The records of `box` as a registration writes them (slot 1, set1): its width and height (FRAME_TRAVEL's own box
    entry), its defaults (the definition's "<box> box: default width" and "... height"), the box in use (the entry all
    three share) and every record of its place, the box in use's among them."""
    if box not in BOXES:
        sys.exit(f"boxsize_run: --box {box!r} is none of Custom 1, Custom 2 or Custom 3")
    names = {s.get("name"): s["key"] for s in doc.get("settings") or []}
    plain = [b for b in table.get("boxes") or [] if box in b["areas"]]
    own = next((b for b in plain if not any(x in b["areas"] for x in BOXES if x != box)), None)
    in_use = next((b for b in plain if b is not own), None)
    dw, dh = names.get(f"{box} box: default width"), names.get(f"{box} box: default height")
    if own is None or not dw or not dh:
        sys.exit(f"boxsize_run: the hand tables or the definition do not name {box}'s size and default records")

    def s1(k):
        return k.replace("set:", "set1:", 1)
    return {"box": box, "width": s1(own["size"][0]), "height": s1(own["size"][1]), "default_width": s1(dw),
            "default_height": s1(dh), "in_use_width": s1(in_use["size"][0]) if in_use else None,
            "in_use_height": s1(in_use["size"][1]) if in_use else None,
            "places": [(s1(x), s1(y)) for x, y in own["places"] + (in_use["places"] if in_use else [])],
            "areas": list(own["areas"])}


def size_of(cs, recs: dict) -> dict:
    """The box's size records as the settings file `cs` (a registration's download) holds them."""
    from prove_run import held_value
    return {k: held_value(cs, recs[k]) if recs.get(k) else None
            for k in ("width", "height", "default_width", "default_height", "in_use_width", "in_use_height")}


def place_of(cs, recs: dict) -> dict:
    """{key: value} of every record of the box's place in `cs`."""
    from prove_run import held_value
    return {k: held_value(cs, k) for pair in recs["places"] for k in pair}


def rule_of(entry: dict) -> dict:
    """{"x": limit, "y": limit}: FRAME_TRAVEL's rule for a Custom box on each axis as the definition writes it
    (kit/writer/frames.placed: the bounds, the grid and each Aspect Ratio's picture), the same for every box's place."""
    _, _, lims = frames.placed(entry)[0]
    return {a: lims[a][0] for a in frames.AXES}


def predicted(lim: dict, size, value) -> list | None:
    """[low, high] the box's centre may take on one axis by the rule (`lim`: rule_of's, for that axis) at the box's
    `size` and the Aspect Ratio `value`: kit/writer/frames.box_limits, the one implementation; None where the rule has
    no picture for `value`, or the box does not fit."""
    if size is None:
        return None
    got = frames.box_limits(lim, size, value)
    return list(got) if got is not None and got[0] <= got[1] else None


def travel_check(edges: list, recs: dict, rule: dict, size: dict, value) -> list:
    """Each measured record of the box's place (edges: edge_records' {"key", "low", "high"}) against the rule (`rule`:
    rule_of's) at `size` and the Aspect Ratio `value`: {"key", "axis", "measured", "predicted", "match", "diff"} (diff:
    measured less predicted, low and high); a measured record that is no place of the box is left out."""
    axes = {}
    for kx, ky in recs["places"]:
        axes[kx], axes[ky] = "x", "y"
    out = []
    for e in edges:
        ax = axes.get(e["key"])
        if ax is None:
            continue
        p = predicted(rule[ax], size.get("width" if ax == "x" else "height"), value)
        m = [e["low"], e["high"]]
        out.append({"key": e["key"], "axis": ax, "measured": m, "predicted": p, "match": p == m,
                    "diff": [m[0] - p[0], m[1] - p[1]] if p else None})
    return out


def travel_words(c: dict, values: bool = True) -> str:
    """A travel check in words: the limits measured and the rule's (`values`; else neither: a start size that is the
    owner's), then match or each limit's difference."""
    if c["predicted"] is None:
        said = "the rule leaves the box no place at this size"
    elif c["match"]:
        said = "match"
    else:
        said = ", ".join(f"{w} {d:+d}" for w, d in zip(("low", "high"), c["diff"], strict=True) if d)
    if not values:
        return said if c["match"] or c["predicted"] is None else f"differs from the rule: {said}"
    rule = "" if c["predicted"] is None else f", the rule {c['predicted'][0]} to {c['predicted'][1]}"
    return f"measured {c['measured'][0]} to {c['measured'][1]}{rule}: {said}"


def steps_of(values: list) -> list:
    """The steps between sizes registered one click apart."""
    return [b - a for a, b in zip(values, values[1:], strict=False)]


def pattern_words(steps: list) -> str:
    """The steps said, and their pattern: one step a click, or the shortest run that repeats ("16 every 3 clicks"; the
    whole run where it is too short to show a repeat), or a click that changed nothing."""
    said = ", ".join(str(x) for x in steps)
    if not steps:
        return "no click"
    if 0 in steps:
        return f"{said} (a click changed nothing)"
    if len(set(steps)) == 1:
        return f"{said} ({steps[0]} a click)"
    for p in range(2, len(steps) + 1):
        if all(steps[i] == steps[i + p] for i in range(len(steps) - p)):
            return f"{said} ({sum(steps[:p])} every {p} clicks)"
    return said


def seek_clicks(cur: int, target: int, unit: float) -> int:
    """The clicks that should bring `cur` to `target` at `unit` a click, one at least."""
    n = round((target - cur) / unit)
    return n or (1 if target > cur else -1)


def unreachable(seen: dict, target: int) -> bool:
    """Whether the sizes registered on the way back (`seen`: {net clicks: size}) hold two a click apart either side of
    `target`: no click lands on it from there."""
    pos = sorted(seen)
    return any(b - a == 1 and min(seen[a], seen[b]) < target < max(seen[a], seen[b]) for a, b in zip(pos, pos[1:], strict=False))


def aspect_of(index: dict, cs) -> tuple:
    """(code, label) of the Aspect Ratio the settings file `cs` holds, the label the definition gives the code (None
    where it names none); (None, None) not read."""
    from prove_run import held_value
    s = next((s for s in index.values() if s.get("name") == "Aspect Ratio" and s.get("values")), None)
    code = held_value(cs, s["key"]) if s else None
    return (None, None) if code is None else (code, dict((v, lab) for v, lab in s["values"]).get(code))


def context_of(aspect: str | None, amt: str | None = "Standard") -> str:
    """The state the sizes are measured in: framepos_run's context, the camera level (Switch V/H AF Area Off), AF Frame
    Move Amt where the run sets it, then the Aspect Ratio the start download holds."""
    return F.context_of(None, amt, None, None) + f", Aspect Ratio {aspect or 'not read'}"


def chooser_refused(kind, text, lit, box: str) -> str:
    """Why SET (C4) may not go here, or "": only on Focus Area's chooser (a dialog, its title read), its trash button
    reading SET (as it does with a Custom box lit; a glyph run onto it, "ISET", aside), the lit area `lit` that box."""
    if kind != "dialog":
        return f"the screen reads as {kind!r}, not Focus Area's chooser"
    if not re.search(r"focus\s*area", str(text or ""), re.I) or not re.search(r"SET\b", str(text or "")):
        return "the screen does not read as Focus Area's chooser with SET on its trash button"
    if bare(lit or "") != bare(box):
        return f"the lit area reads {str(lit or '').strip()[:30]!r}, not {box}"
    return ""


def editor_refused(kind, text, box: str) -> str:
    """Why a dial, or the editor's OK, may not go here, or "": only on `box`'s own size editor, a screen of no known
    kind whose text starts with the box's name and holds Reset and Cancel after it (kit2_freesize)."""
    if kind not in EDITOR_KINDS:
        return f"the screen reads as {kind!r}, not {box}'s size editor (a screen of no known kind)"
    if not re.search(EDITOR_RE.format(n=box.split()[-1]), str(text or ""), re.I):
        return f"the screen does not read as {box}'s size editor (its title, then Reset and Cancel)"
    return ""


def editor_box(image) -> list | None:
    """[x0, y0, x1, y1] of the box the size editor draws in orange (BOX_BAND), in pixels; None where none is found.
    Kept beside each size: the registration is the judge."""
    if image is None:
        return None
    import numpy as np

    from camkit import screen
    band = screen._orange(image)[BOX_BAND[0]:BOX_BAND[1]] > 0.5
    ys, xs = np.nonzero(band)
    if len(xs) < 50:
        return None
    return [int(xs.min()), int(ys.min()) + BOX_BAND[0], int(xs.max()), int(ys.max()) + BOX_BAND[0]]


def memory_allowed(allow) -> bool:
    return F.memory_allowed(allow)


def named_in(word: str, allow) -> bool:
    want = safety.clean_label(safety.fold(word))
    return any(safety.clean_label(safety.fold(x)) == want for x in allow or ())


def set_allowed(allow) -> bool:
    return named_in(SET_WORD, allow)


def reset_allowed(allow) -> bool:
    """Whether the run has the owner's word for the size editor's Reset (RESET_WORD)."""
    return named_in(RESET_WORD, allow)


def setup_words(probe: bool, tracking: bool) -> list:
    """The setup through the menu, as framepos_run sets it: Switch V/H AF Area Off; with the edges, Circ. of Focus Point
    and AF Frame Move Amt Standard; with --tracking, Focus Mode Continuous AF and its dials."""
    return [afreg_run.step_name(k, w) for k, w in F.setup_steps(tracking, tracking, None if probe else "Standard", None,
                                                                not probe)]


def plan_lines(a, recs: dict) -> list:
    """What a run will do, for --list (and before a run): nothing is sent."""
    box = recs["box"]
    out = [f"{box}: width {recs['width']} (rear_l), height {recs['height']} (front); defaults {recs['default_width']}, "
           f"{recs['default_height']}; the box in use {recs['in_use_width']}, {recs['in_use_height']}; its place "
           + ", ".join(f"{x}/{y}" for x, y in recs["places"]),
           f"set through the menu first: {'; '.join(setup_words(bool(a.probe), a.tracking))}; the start file put back at "
           "the end puts them back",
           "each size: Focus Area's chooser with the box lit, SET (C4), the dials turned only on the box's own editor, "
           f"OK kept with the camera's consent for that editor, slot 1 registered ({F.MEMORY_ROW}) and its size read"]
    if a.probe:
        out.append(f"probe: {a.probe} {a.clicks} single clicks up, each registered, then {a.clicks} down, each "
                   "registered: the steps near the start size and whether they come back to it exactly")
        n = 2 * a.clicks + 2
    else:
        for dial in a.dials:
            out.append(f"{dial} ({DIALS[dial]}): turns of {a.block} clicks toward its smallest until {a.confirm} clicks "
                       f"more change nothing, {a.pattern} single clicks up from it; the same toward its largest and "
                       f"{a.pattern} down from it; then back to the start {DIALS[dial]} by counted clicks")
        odd = ", ".join(f"{d} {n:+d}" for d, n in ODD)
        out.append(f"edges measured at the start size, at each dial's smallest and largest, and at one odd size ({odd} "
                   "clicks), as framepos_run.py --edges measures them, each against the rule (kit/writer/frames.box_limits "
                   "on FRAME_TRAVEL's rule, at the Aspect Ratio the start download holds)")
        if a.tracking:
            out.append("at the odd size, Tracking: Custom chosen and registered: does the box in use read the box's size")
        n = len(a.dials) * (2 * 2 * 2 + 2 * a.pattern + 2) + 4 + len(F.EDGE_TAGS + ("back",)) * (2 * len(a.dials) + 2)
    out.append(f"about {n} registrations, {round(n * (F.REG_S + F.CHOOSE_S) / 60)} minutes at most")
    if getattr(a, "reset", False):
        back = ("then the editor's Reset (the trash button) where the clicks cannot land on a start size that is the "
                f"default records' ({RESET_WORD}, the owner's word, 2026-11-17)")
    else:
        back = (f"a default start size the clicks cannot land on again is put back by the editor's Reset only with "
                f"--allow {RESET_WORD!r}")
    out.append(f"the size is put back by counted clicks, each landing registered; {back}; a start size neither brings "
               "back is said, never guessed: --put-back RUN tries again, or set it by hand in the editor")
    return out


# ---------------------------------------------------------------- the camera

def turn(cam, box: str, dial: str, clicks: int) -> None:
    """`dial` turned `clicks` (signed) on `box`'s size editor, one command a click, a step of one: the a1 II moves the
    box one click a command, whatever its steps (kit2_boxsize_c1_width: "dial rear_l -10" moved 16 units, a click).
    Each click goes only once the screen read just before it (the first read here, the others after the click before:
    LiveCamera.dial reads it) is that editor (editor_refused): never the shooting screen, where a dial changes the live
    exposure (the link refuses a dial there besides), nor any other screen. Failed, nothing more turned, else."""
    from camkit.live import text_of
    from prove_run import Failed
    if dial not in DIALS:
        raise Failed(f"{dial!r} is no dial of the size editor (rear_l: the width, front: the height): no dial turned")
    step = 1 if clicks > 0 else -1
    s = cam.refresh("before-dial") if clicks else None
    for _ in range(abs(int(clicks))):
        why = editor_refused(s.kind, text_of(cam), box)
        if why:
            raise Failed(f"{why}: no dial turned ({cam.frame.path.name})")
        s = cam.dial(dial, step)


def press_reset(cam, box: str) -> None:
    """The size editor's Reset: C4, allowed by name, on `box`'s editor read just before (editor_refused), with the
    camera's consent for that one press on that editor (camkit.live.BoxReset: the editor judged by its own shape, and the
    link handed the size editor kind decision 7 names for it). The screen after it must read as the same
    editor, the box redrawn at its default size (kit2_freesize 00563 -> 00564); a question or any other screen stops the
    walk there, nothing pressed after the C4 here (the session's close leaves it with MENU, as every run's), what showed
    kept in the run's events. The callers judge the size by the registration after OK (Sizes.reset_back)."""
    from camkit.live import BoxReset, text_of
    from prove_run import Failed
    why = editor_refused(cam.read().kind, text_of(cam), box)
    if why:
        raise Failed(f"{why}: no Reset ({cam.frame.path.name})")
    cam.answer_once = BoxReset(f"{box}'s size editor: Reset puts the default size back ({RESET_WORD}, the owner's word, "
                               "2026-11-17)", box)
    cam.press("c4", allow=frozenset({"c4"}))
    kind = cam.read().kind
    why = editor_refused(kind, text_of(cam), box)
    if why:
        name = afreg_run.kept_notice(cam, f"Reset in {box}'s size editor", None, "reset_screen")
        raise Failed(f"Reset in {box}'s size editor brought {kind!r}, not the editor ({name}): nothing answered; what it "
                     "showed is in the run's events.jsonl")


def keep_size(cam, box: str) -> None:
    """OK in `box`'s size editor, read as that editor just before (editor_refused), with the camera's consent for that
    one press on that editor (camkit.live.BoxEditor): the size kept, the shooting screen. A notice after it is kept in
    the run's events and fails the size; any other screen than the shooting screen, looked at again, fails it too."""
    from camkit.live import BoxEditor, text_of
    from prove_run import Failed
    why = editor_refused(cam.read().kind, text_of(cam), box)
    if why:
        raise Failed(f"{why}: no OK ({cam.frame.path.name})")
    cam.answer_once = BoxEditor(f"{box}'s size editor: OK keeps its size ({SET_WORD}, the owner's word)", box)
    cam.press("enter")
    kind = cam.read().kind
    if kind not in ("shooting", "notice"):
        time.sleep(1.0)
        kind = cam.refresh("after-ok").kind
    if kind == "notice":
        name = afreg_run.kept_notice(cam, f"OK in {box}'s size editor", None, "editor_notice")
        cam.press("menu")
        raise Failed(f"a notice after OK in {box}'s size editor ({name}; its words are in the run's events.jsonl)")
    if kind != "shooting":
        raise Failed(f"after OK in {box}'s size editor the screen reads as {kind!r}, not the shooting screen "
                     f"({cam.frame.path.name})")


def open_editor(sw) -> None:
    """`sw`'s box's size editor opened: MENU, Focus Area by the scan, Right, the box under the carousel's cursor
    (afreg_run.choose_level, every step read), the chooser read as Focus Area's with that box lit and SET on its trash
    button (chooser_refused: the lit axis value read again), SET (C4, allowed by name), the editor read as the box's own
    (editor_refused); Failed else, what showed kept in the run's events."""
    from camkit.live import text_of
    from prove_run import Failed, axis_reading
    from proving.screens import carousel_text
    cam, box, (i, o, v) = sw.cam, sw.box, sw.r
    afreg_run.choose_level(cam, sw.cycle, sw.model, sw.labels, sw.axes, i, o, v)
    vals = sw.axes[o]["values"] if o else None
    got = axis_reading(cam, vals)[0] if vals else None
    lit = vals[got] if got is not None else carousel_text(cam)
    why = chooser_refused(cam.read().kind, text_of(cam), lit, box)
    if why:
        raise Failed(f"SET not pressed: {why} ({cam.frame.path.name})")
    cam.press("c4", allow=frozenset({"c4"}))
    why = editor_refused(cam.read().kind, text_of(cam), box)
    if why:
        name = afreg_run.kept_notice(cam, f"SET on {box}", None, "editor_screen")
        raise Failed(f"SET on {box} opened no editor of its own: {why} ({name}; what showed is in the run's events.jsonl)")


class Sizes:
    """One box's size walk: each size set in its editor and kept (point_turns), slot 1 registered and read (register,
    through framepos_run.Walk), the ends (to_end), the steps (pattern), the way back (seek, and the editor's Reset:
    back_to_start), the edges at a size (travel), the probe, the odd size, the put-back and the finish. `rule`: rule_of's,
    judged at the Aspect Ratio `aspect` (its code); `tag`: the context and allowance every line carries; a.reset: whether
    the run has the owner's word for the editor's Reset."""

    def __init__(self, cam, link, hdmi, run, cycle, model, a, t: dict, r: tuple, labels, axes, recs: dict, rule: dict,
                 tag: dict, index: dict | None = None, aspect=0):
        self.cam, self.link, self.hdmi, self.run, self.cycle, self.model, self.a = cam, link, hdmi, run, cycle, model, a
        self.t, self.r, self.labels, self.axes, self.recs, self.rule, self.tag = t, r, labels, axes, recs, rule, tag
        self.index, self.box, self.aspect = index or {}, t["label"], aspect
        self.amt_state = {"now": "Standard"}
        self.walk = F.Walk(cam, link, hdmi, run, cycle, model, a, None, t, "size", self.amt_state)
        self.out = run.dir / OUT
        self.n, self.units, self.start_travel, self.missed, self.reset_failed = 0, {}, None, {}, False
        self.start_size = self.size = self.start_place = self.place = None
        self.default = True

    def write(self, line: dict) -> None:
        jsonl.append(self.out, {"t": round(time.time(), 3), "box": self.box, **line, **self.tag})

    def value(self, dim: str, v, absolute: bool = False) -> str:
        """A size as said: its value, or, from a start that is the owner's, its difference from the start."""
        if absolute or self.default or v is None or (self.start_size or {}).get(dim) is None:
            return str(v)
        return f"{v - self.start_size[dim]:+d} from the start"

    def say(self, size: dict, absolute: bool = False) -> str:
        return f"width {self.value('width', size['width'], absolute)}, height {self.value('height', size['height'], absolute)}"

    def register(self, what: str) -> tuple:
        """Slot 1 registered and downloaded (framepos_run.Walk.reg): (its tag, the box's size, its place)."""
        self.n += 1
        tag = f"{self.n:03d}-{slug(what)}"
        self.walk.reg(tag)
        cs = self.walk.cs[tag]
        return tag, size_of(cs, self.recs), place_of(cs, self.recs)

    def start(self) -> dict:
        """The box registered where the run finds it: the start size and place; whether the size is the defaults'.
        Failed, nothing turned, where the registration holds no size."""
        from prove_run import Failed
        tag, size, place = self.register("start")
        if size["width"] is None or size["height"] is None:
            raise Failed(f"slot 1 registered holds no size for {self.box} ({self.recs['width']}, {self.recs['height']}): "
                         "nothing was turned")
        self.start_size, self.size, self.start_place, self.place = size, size, place, place
        self.default = size["width"] is not None and (size["width"], size["height"]) == (size["default_width"],
                                                                                         size["default_height"])
        self.write({"what": "start", "file": self.walk.files[tag], "size": size, "place": place, "default": self.default})
        print(f"  start: {self.box} " + (f"{self.say(size)} (the defaults')" if self.default else
                                         "at a size that is not the defaults' (the owner's: not said; the sizes reached "
                                         "from it are said by their difference from it)"), flush=True)
        return size

    def point_turns(self, turns: list, what: str, absolute: bool = False) -> dict:
        """One size: the editor opened (open_editor), each (dial, clicks) turned on it (turn), the editor's box measured,
        OK (keep_size), slot 1 registered and read; the line written, the place's move since the last registration kept
        by delta; returns the size."""
        open_editor(self)
        for dial, n in turns:
            turn(self.cam, self.box, dial, n)
        drawn = editor_box(getattr(self.cam.frame, "image", None))
        keep_size(self.cam, self.box)
        tag, size, place = self.register(what)
        moved = [{"key": k, "delta": place[k] - self.place[k]} for k in place
                 if place[k] is not None and self.place.get(k) is not None and place[k] != self.place[k]]
        self.write({"what": what, "turns": [list(x) for x in turns], "file": self.walk.files[tag], "size": size,
                    "place": place, "screen_box": drawn, **({"place_moved": moved} if moved else {})})
        said = ", ".join(f"{d} {n:+d}" for d, n in turns)
        print(f"  {what}: {said} -> {self.say(size, absolute)}"
              + ("; the box's place moved with its size: " + ", ".join(f"{m['key']} {m['delta']:+d}" for m in moved)
                 if moved else ""), flush=True)
        self.size, self.place = size, place
        return size

    def point(self, dial: str, clicks: int, what: str, absolute: bool = False) -> dict:
        return self.point_turns([(dial, clicks)], what, absolute)

    def to_end(self, dial: str, sign: int) -> int:
        """Turns of a.block clicks toward the dial's smallest (sign -1) or largest, each followed by a.confirm clicks
        more, until those change nothing: the end, written and said by value (a camera fact)."""
        from prove_run import Failed
        dim, word = DIALS[dial], "smallest" if sign < 0 else "largest"
        for _ in range(ENDS_TRIES):
            self.point(dial, sign * self.a.block, f"{dial} toward its {word}")
            before = self.size[dim]
            self.point(dial, sign * self.a.confirm, f"{dial} toward its {word}, checked")
            if self.size[dim] == before:
                self.write({"what": "end", "dial": dial, "end": word, "size": self.size})
                print(f"  {dial} {word}: {dim} {before} ({self.a.confirm} clicks more changed nothing)", flush=True)
                return before
        raise Failed(f"{dial}: its {word} {dim} not reached in {ENDS_TRIES} turns of {self.a.block} clicks")

    def pattern(self, dial: str, sign: int, n: int) -> list:
        """`n` single clicks from where the box is, each kept and registered: the steps (said by value: from an end)."""
        dim, values = DIALS[dial], [self.size[DIALS[dial]]]
        for _ in range(n):
            values.append(self.point(dial, sign, f"{dial} {'up' if sign > 0 else 'down'} one click", True)[dim])
        steps = steps_of(values)
        moved = [abs(x) for x in steps if x]
        if moved:
            self.units[dial] = sum(moved) / len(moved)
        return steps

    def seek(self, dial: str, target) -> bool:
        """The dial's size brought to `target` (the start's) by counted clicks (seek_clicks at the steps measured, else
        UNIT), each landing kept and registered, SEEK_TRIES at most; stops where no click lands on it (unreachable) or a
        turn changed nothing (an end lies before it), keeping why (missed) for back_to_start to say or make good."""
        dim = DIALS[dial]
        cur, seen, pos, stuck = self.size[dim], {}, 0, False
        seen[0] = cur
        for _ in range(SEEK_TRIES):
            if cur == target or unreachable(seen, target):
                break
            n = seek_clicks(cur, target, self.units.get(dial) or UNIT[dial])
            v = self.point(dial, n, f"{dial} back to its start")[dim]
            pos += n
            seen[pos] = v
            stuck, cur = v == cur, v
            if stuck:
                break
        if cur == target:
            print(f"  {self.box}'s {dim} back at its start size (registered)", flush=True)
            return True
        self.missed[dial] = ("no click lands on it from here" if unreachable(seen, target) else
                             "a turn changed nothing: an end of the dial lies before it" if stuck else
                             f"not reached in {SEEK_TRIES} landings")
        return False

    def can_reset(self) -> bool:
        """Whether the editor's Reset may put the box back: the start size the default records' (a Reset restores
        exactly what the run found), the owner's word given (--allow RESET_WORD), and no Reset of the run's gone wrong."""
        return bool(self.default and getattr(self.a, "reset", False) and not self.reset_failed)

    def reset_back(self) -> bool:
        """The box put back by its editor's Reset (can_reset): the editor opened, Reset (press_reset: a screen other than
        the editor stops the walk, nothing answered, and no Reset is tried again), OK kept, slot 1 registered, the size
        judged against the default records and the start's; a Reset that does not give both is said, and not tried
        again."""
        from prove_run import Failed
        open_editor(self)
        try:
            press_reset(self.cam, self.box)
        except Failed:
            self.reset_failed = True
            raise
        keep_size(self.cam, self.box)
        tag, size, place = self.register("reset")
        dims = ("width", "height")
        back = all(size[d] == size[f"default_{d}"] == self.start_size[d] for d in dims)
        self.write({"what": "reset", "file": self.walk.files[tag], "size": size, "place": place, "back": back})
        self.size, self.place = size, place
        if back:
            print(f"  {self.box} put back by its editor's Reset: {self.say(size)}, the default records' and the start's",
                  flush=True)
            return True
        self.reset_failed = True
        print("  the editor's Reset did not put it back: "
              + ", ".join(f"{d} {size[d] - self.start_size[d]:+d}" for d in dims if size[d] != self.start_size[d])
              + f" off its start, the default records reading {size['default_width']} x {size['default_height']}",
              flush=True)
        return False

    def not_put_back(self, dial: str, why: str) -> None:
        """A dimension the walk could not bring back, said with what to do by hand (and, from a default start, the word
        that lets the editor's Reset do it), written."""
        dim = DIALS[dial]
        off = self.size[dim] - self.start_size[dim]
        self.write({"what": "not put back", "dial": dial, "off": off, "why": why})
        hint = ""
        if self.default and not getattr(self.a, "reset", False):
            hint = f"; with --allow {RESET_WORD!r} the editor's Reset puts back the default size, which it began at"
        elif self.default:
            hint = "; there its Reset (the trash button) puts back the default size, which it began at"
        print(f"  NOT PUT BACK: {self.box}'s {dim} is {off:+d} off its start, {why}: on the camera, Focus Area, {self.box}, "
              f"SET (the trash button), turn {DIAL_WORDS[dial]} and OK{hint}; or run {PROG} --put-back "
              f"{self.run.dir.name}", flush=True)

    def back_to_start(self, dials=None) -> bool:
        """Every dimension of `dials` (all) off its start brought back by counted clicks (seek), each tried whatever the
        other did; what the clicks cannot reach, by the editor's Reset where it may (can_reset, reset_back); what neither
        brings back said (not_put_back)."""
        off = [d for d in (dials or DIALS) if self.size[DIALS[d]] != self.start_size[DIALS[d]]]
        if not off:
            print(f"  {self.box} back at its start size (registered)", flush=True)
            return True
        missed = [d for d in off if not self.seek(d, self.start_size[DIALS[d]])]
        if missed and self.can_reset() and self.reset_back():
            return True
        for d in missed:
            if self.size[DIALS[d]] != self.start_size[DIALS[d]]:
                self.not_put_back(d, self.missed.get(d) or "")
        return not missed

    def probe(self, dial: str, n: int) -> bool:
        """--probe: `n` single clicks up, each registered, then `n` down: the steps said, the size back at its start (seek
        makes good what the clicks did not)."""
        dim = DIALS[dial]
        values = [self.size[dim]]
        for _ in range(n):
            values.append(self.point(dial, 1, f"{dial} up one click")[dim])
        up = steps_of(values)
        values = [self.size[dim]]
        for _ in range(n):
            values.append(self.point(dial, -1, f"{dial} down one click")[dim])
        down = steps_of(values)
        self.write({"what": "probe steps", "dial": dial, "up": up, "down": down})
        print(f"  {dial} up: {pattern_words(up)}\n  {dial} down: {pattern_words(down)}", flush=True)
        moved = [abs(x) for x in up + down if x]
        if moved:
            self.units[dial] = sum(moved) / len(moved)
        return self.back_to_start([dial])

    def measure_travel(self, what: str) -> dict:
        """The edges at the size the box has (framepos_run.edge_area, under Standard, the frame brought back to where
        the measure began), the size read from its start registration; written to the run's edges.jsonl."""
        from camkit import camset
        line = F.edge_area(self.cam, self.link, self.hdmi, self.run, self.cycle, self.model, self.labels, self.axes,
                           self.t, self.r, self.a, self.index, None, "Standard", self.amt_state)
        base = (line.get("files") or {}).get("base")
        line.update(self.tag, at=what, size=size_of(camset.read(self.run.dat / base), self.recs) if base else None)
        jsonl.append(self.run.dir / "edges.jsonl", line)
        return line

    def travel(self, what: str) -> dict:
        """The edges at this size (measure_travel), each record of the box's place judged against the rule
        (travel_check), written and said: from a start size that is the owner's, every size but a dial's ends said by
        its difference from the start and its limits by match or difference alone. Failed where the measure left the
        frame away from where it began: the walk stops there."""
        from prove_run import Failed
        line = self.measure_travel(what)
        size = line.get("size") or self.size
        check = travel_check(line.get("edges") or [], self.recs, self.rule, size, self.aspect)
        end = what.endswith(("smallest", "largest"))            # a dial's end: a camera fact, said by value
        values = self.default or end
        self.write({"what": "travel", "at": what, "size": size, "check": check,
                    "back": (line.get("back") or {}).get("same"), **({"failed": line["failed"]} if line.get("failed") else {})})
        if what == "start":
            self.start_travel = line
        head = f"  travel at {what} ({self.say(size, end)})"
        print("\n".join([head] + [f"    {c['key']}: {travel_words(c, values)}" for c in check]
                        + ([f"    failed: {line['failed']}"] if line.get("failed") else [])), flush=True)
        if line.get("moved") and not (line.get("back") or {}).get("same"):
            raise Failed(f"the edges at {what} left {self.box}'s frame away from where it began")
        return line

    def measure_dial(self, dial: str) -> bool:
        """One dial: its smallest (to_end), the edges there, the steps up from it, its largest, the edges there, the
        steps down from it, then back to the start (back_to_start: clicks, else the editor's Reset where it may)."""
        for sign, word, step in ((-1, "smallest", "up"), (1, "largest", "down")):
            self.to_end(dial, sign)
            self.travel(f"{dial} {word}")
            steps = self.pattern(dial, -sign, self.a.pattern)
            self.write({"what": "pattern", "dial": dial, "from": word, "steps": steps})
            print(f"  {dial} {step} from the {word}: {pattern_words(steps)}", flush=True)
        return self.back_to_start([dial])

    def tracking(self, tr: tuple) -> dict:
        """Tracking: <box> chosen (route `tr`) and registered: does the box in use read the box's own size."""
        from prove_run import to_shooting
        afreg_run.choose_area(self.cam, self.run, self.cycle, self.model, self.labels, self.axes, tr, None)
        to_shooting(self.link, self.hdmi, "the shooting screen with Tracking chosen")
        tag, size, place = self.register(f"tracking {self.box}")
        shares = (size["in_use_width"], size["in_use_height"]) == (size["width"], size["height"])
        self.write({"what": "tracking", "file": self.walk.files[tag], "size": size, "shares": shares})
        print(f"  Tracking: {self.box} chosen: the box in use reads {'the same size as' if shares else 'another size than'} "
              f"{self.box}'s", flush=True)
        self.size, self.place = size, place
        return size

    def odd(self, tr: tuple | None = None) -> bool:
        """The odd size (ODD from the start), the edges there, Tracking's size beside it (`tr`), the turns undone."""
        self.point_turns(list(ODD), "the odd size")
        self.travel("the odd size")
        if tr is not None:
            self.tracking(tr)
        self.point_turns([(d, -n) for d, n in ODD], "the odd size undone")
        return self.back_to_start()

    def put_back(self, start_line: dict) -> bool:
        """--put-back: the box registered where it is now, and brought back to `start_line`'s size (a run's start) by
        counted clicks, else by the editor's Reset where it may (back_to_start), each landing registered; already there,
        nothing turned."""
        self.start_size, self.start_place = start_line["size"], start_line.get("place") or {}
        self.default = bool(start_line.get("default"))
        tag, size, place = self.register("now")
        self.size, self.place = size, place
        self.write({"what": "now", "file": self.walk.files[tag], "size": size, "place": place,
                    "source": start_line.get("file")})
        if (size["width"], size["height"]) == (self.start_size["width"], self.start_size["height"]):
            print(f"  {self.box} already at its start size", flush=True)
            return True
        return self.back_to_start()

    def finish(self) -> bool:
        """Slot 1 registered once more: the size and place judged against the start's. A place off is brought back
        from the edges measured at the start size (framepos_run.put_back_area) where they were; said either way."""
        tag, size, place = self.register("finish")
        self.size, self.place = size, place
        off = {d: size[d] - self.start_size[d] for d in ("width", "height") if size[d] != self.start_size[d]}
        moved = {k: v - self.start_place[k] for k, v in place.items()
                 if v is not None and self.start_place.get(k) is not None and v != self.start_place[k]}
        if moved and not off and self.start_travel:
            moved = self.place_back(moved)
        self.write({"what": "finish", "file": self.walk.files[tag], "size": size, "place": place, "size_off": off,
                    "place_off": moved})
        if not off and not moved:
            print(f"  {self.box} back at its start size and place (registered)", flush=True)
            return True
        for d, n in off.items():
            print(f"  NOT PUT BACK: {self.box}'s {d} is {n:+d} off its start: run {PROG} --put-back "
                  f"{self.run.dir.name}", flush=True)
        if moved:
            print(f"  NOT PUT BACK: {self.box}'s place is off its start ("
                  + ", ".join(f"{k} {n:+d}" for k, n in moved.items()) + f"): run {PROG} --put-back "
                  f"{self.run.dir.name}, or move it back by hand", flush=True)
        return False

    def place_back(self, moved: dict) -> dict:
        """The box's place brought back to the start's from the edges measured at the start size, as framepos_run.py
        --put-back brings a frame (put_back_area); returns what is still off."""
        m, why = F.put_back_plan(self.start_travel)
        if m is None:
            print(f"  the box's place cannot be brought back here: {why}", flush=True)
            return moved
        a = argparse.Namespace(**{**vars(self.a), "put_back": self.run.dir.name})
        line = F.put_back_area(self.cam, self.link, self.hdmi, self.run, self.cycle, self.model, self.labels, self.axes,
                               self.t, self.r, a, self.index, None, self.start_travel, m)
        jsonl.append(self.run.dir / "put_back.jsonl", dict(line, **self.tag))
        if (line.get("back") or {}).get("same"):
            return {}
        return {x["key"]: x["delta"] for x in (line.get("back") or {}).get("off") or []} or moved


def aspect_known(index: dict, cs, rule: dict) -> tuple:
    """(code, label) of the Aspect Ratio the start download `cs` holds, the rule having a picture for it on both axes;
    Failed, nothing pressed, where it reads none or the rule has no picture for it."""
    from prove_run import Failed
    code, label = aspect_of(index, cs)
    if code is None:
        raise Failed("the start download's Aspect Ratio reads nothing: the rule needs it; nothing was pressed")
    if any(predicted(rule[a], 0, code) is None for a in frames.AXES):
        raise Failed(f"the start download's Aspect Ratio reads {label or code}: the rule (FRAME_TRAVEL's pictures) has no "
                     "picture for it; nothing was pressed")
    return code, label


def body(s, a, run, hdmi, cycle, model, labels, axes, index, recs, rule, t, r, tr, tag) -> bool:
    """The session's body: slot 1 filled in the start file and its Aspect Ratio one the rule has a picture for (else
    nothing pressed), the setup, the box chosen and its start registered, then the probe or every dial and the odd size;
    a walk that stops brings the size back first; the finish judges size and place."""
    from camkit import camset
    from prove_run import Failed, to_shooting
    from runner import close_screen
    cam, link = s.cam, s.link
    start = camset.read(s.start)
    if not F.slot_filled(start):
        raise Failed("slot 1 is empty in the start file: registering it would mark it filled for good; this run "
                     "registers a filled slot only")
    code, label = aspect_known(index, start, rule)
    tag["context"] = context_of(label, None if a.probe else "Standard")
    tag["setup"] = F.prepare(cam, link, hdmi, run, cycle, model, a.tracking, a.tracking, s.start,
                             None if a.probe else "Standard", index, None, circ=not a.probe)
    sw = Sizes(cam, link, hdmi, run, cycle, model, a, t, r, labels, axes, recs, rule, tag, index, code)
    try:
        afreg_run.choose_area(cam, run, cycle, model, labels, axes, r, None)
        to_shooting(link, hdmi, "the shooting screen with the box chosen")
        sw.start()
        ok = True
        try:
            if a.probe:
                ok = sw.probe(a.probe, a.clicks)
            else:
                sw.travel("start")
                for dial in a.dials:
                    ok = sw.measure_dial(dial)
                    if not ok:
                        break
                ok = ok and sw.odd(tr)
        except Failed as e:
            print(f"  stopped: {e}", flush=True)
            close_screen(cam, link)
            to_shooting(link, hdmi, "the shooting screen to put the size back")
            ok = sw.back_to_start() and False
        return sw.finish() and ok
    except BaseException as e:
        say_trace(e)
        print(f"  {recs['box']} may be left at another size or place: run {PROG} --allow {F.MEMORY_ROW!r} --allow "
              f"{SET_WORD!r}{f' --allow {RESET_WORD!r}' if sw.default else ''} --put-back {run.dir.name}", flush=True)
        raise


def session_parts(a, doc: dict, box: str) -> tuple:
    """(labels, axes, route of the box, route of its Tracking form or None, its plan entry) from pass 1's map and the axis
    walk; exits where they do not name the box once."""
    from pass3_run import labels_of
    from prove_run import AXES
    labels, kind = labels_of([F.ROW])
    if kind != "dialog":
        sys.exit(f"{F.ROW} is a {kind} in pass 1's map, not a carousel")
    axes = {o: info for o, info in read_json(AXES).get(F.ROW, {}).items() if len(info["values"]) > 1}
    r = afreg_run.route(box, labels, axes)
    tr = afreg_run.route(f"Tracking: {box}", labels, axes) if getattr(a, "tracking", False) else None
    if r is None or (getattr(a, "tracking", False) and tr is None):
        sys.exit(f"pass 1's map and the axis walk ({AXES}) do not name {box} (or its Tracking form) once: walk the axes "
                 "first (kit/axis_walk.py --rows 'Focus Area')")
    return labels, axes, r, tr, F.edge_plan(doc, box)[0]


def prove(a, doc: dict, recs: dict, table: dict, allowance: str) -> int:
    from camkit.frames import eyes_from_config
    from camkit.runs import Run
    from mode_switch import MAY_OPEN
    from runner import load_scan, prover_session
    labels, axes, r, tr, t = session_parts(a, doc, recs["box"])
    index = {s["key"]: s for s in doc.get("settings") or []}
    cycle, model = load_scan(a.scan)
    run = Run(a.run)
    hdmi = eyes_from_config(run)
    tag = {"context": "", **({"allowance": allowance} if allowance else {})}
    ok = False
    with prover_session(run, hdmi, may_open={F.MEMORY_ROW} | (set(MAY_OPEN) if a.tracking else set()), show=0,
                        expected=frozenset(F.EXPECTED_LEFT), end_why="the settings download after the sizes") as s:
        ok = body(s, a, run, hdmi, cycle, model, labels, axes, index, recs, rule_of(table), t, r, tr, tag)
    print(f"{recs['box']}: {'measured and put back' if ok else 'NOT all measured or put back'} "
          f"({paths.shown(run.dir / OUT)})", flush=True)
    return 0 if ok else 1


def put_back_source(name: str) -> tuple:
    """(the start line, the edges line at the start size or None) of the run `name` (its boxsize.jsonl, its
    edges.jsonl), read from its folder alone; exits where it holds no start line: nothing to put back to. A run walks
    one box: its first start line is the start."""
    src = paths.run_root() / name
    starts = [ln for ln in jsonl.read(src / OUT) if ln.get("what") == "start"] if (src / OUT).exists() else []
    if not starts:
        sys.exit(f"boxsize_run: {paths.shown(src / OUT)} holds no start line: nothing to put back to")
    edges = [ln for ln in jsonl.read(src / "edges.jsonl") if ln.get("at") == "start" and ln.get("area") == starts[0]["box"]] \
        if (src / "edges.jsonl").exists() else []
    return starts[0], (edges[0] if edges else None)


def box_history(box: str) -> dict:
    """What the camera's runs (their boxsize.jsonl) say of `box`, in the order they began: {"owed": (run, why) or None,
    "began": {run: the run whose start was owed when it began, or None}}. A walk that does not end with its size and
    place back (it stopped before its finish line, or its finish says what was not put back) leaves the box owed to its
    start; a walk that begins while a start is owed starts from a box out of place, whatever it finds, and owes nothing
    of its own; a put-back of the owed run that ends with both back clears it. A size the owner set by hand has no such
    run behind it."""
    top, found = paths.run_root(), []
    for d in sorted(top.iterdir()) if top.is_dir() else []:
        if (d / OUT).is_file():
            lines = [ln for ln in jsonl.read(d / OUT) if ln.get("box") == box]
            if lines:
                found.append((lines[0].get("t") or 0, d.name, lines))
    owed, began = None, {}
    for _, name, lines in sorted(found):
        fin = [ln for ln in lines if ln.get("what") == "finish"]
        clean = bool(fin) and not fin[-1].get("size_off") and not fin[-1].get("place_off")
        src = next((ln.get("source") for ln in lines if ln.get("source")), None)
        if src:                                          # a put-back of the run `src`
            if clean and (owed is None or owed[0] == src):
                owed = None
            continue
        began[name] = owed[0] if owed else None
        if owed is None and not clean:
            owed = (name, "it stopped before its finish" if not fin else "it ended with its size or place not back")
    return {"owed": owed, "began": began}


def left_out(box: str) -> tuple | None:
    """(the run that left `box` out of place, why), where the runs say no put-back since brought it back; else None."""
    return box_history(box)["owed"]


def owed_refusal(box: str, put_back: str | None = None) -> str:
    """Why a camera run may not go, or "": a walk of `box` while an earlier run's start is owed (left_out), which would
    take the box's displaced size for the owner's; a put-back of a run that began while another's start was owed, whose
    start is not the box's. Both name the put-back to run instead."""
    hist = box_history(box)
    words = f"{PROG} --allow {F.MEMORY_ROW!r} --allow {SET_WORD!r} --allow {RESET_WORD!r}"
    if put_back:
        origin = hist["began"].get(put_back)
        if origin:
            return (f"{put_back} began while {origin} had left {box} out of place, so its start is not the box's: put back "
                    f"to {origin}'s start instead: {words} --put-back {origin}")
        return ""
    if hist["owed"]:
        run, why = hist["owed"]
        return (f"{run} left {box} out of place ({why}), and no put-back since brought it back: a walk would take where "
                f"the box is for its start; run {words} --put-back {run} first")
    return ""


def target_travel(edges: dict | None, start: dict) -> dict | None:
    """The edges line at a run's start size made the put-back's target: its start registration ("values" "base") taken
    from the run's start line (its place records, the box's place when the run began), where it holds them; the steps,
    edges and centre stay the line's own (measured at that size)."""
    if not edges:
        return None
    values = dict(edges.get("values") or {})
    base, place = dict(values.get("base") or {}), start.get("place") or {}
    base.update({k: place[k] for k in base if place.get(k) is not None})
    return dict(edges, values=dict(values, base=base))


def say_trace(e: BaseException) -> None:
    """The traceback of an exception that is no Failed, no STOP and no Ctrl-C, printed to the console before the
    session's own end takes over: "stopped: KeyError: 0" alone says nothing of where (2026-11-17)."""
    import traceback

    from camkit.link import StopRequested
    from prove_run import Failed
    if not isinstance(e, Failed | StopRequested | KeyboardInterrupt):
        traceback.print_exception(e, file=sys.stdout)
        sys.stdout.flush()


def put_back_plan_lines(a, start: dict, edges: dict | None, recs: dict, centre: bool = False) -> list:
    """What --put-back RUN will do, for its plan (printed before a run, alone with --list): nothing is sent. The start
    size it returns to (by value where it is the default records'; an owner's, never said), the way: registered where it
    is now, then counted clicks, then, from a default start, the editor's Reset as --allow RESET_WORD allows it or not;
    its place, from RUN's edges at the start size where it has them."""
    box, size, run = start["box"], start.get("size") or {}, a.put_back
    if start.get("default"):
        to = f"width {size.get('width')}, height {size.get('height')} (the default records')"
        reset = (f"where no click lands on it, the editor's Reset (the trash button), --allow {RESET_WORD!r} given"
                 if a.reset else f"where no click lands on it, the editor's Reset only with --allow {RESET_WORD!r} "
                 "(not given): else the difference is said")
        way = f"registered where it is now; then by counted clicks, each landing registered; {reset}"
    else:
        to = "a size that is not the defaults' (the owner's, not said)"
        way = ("registered where it is now; then by counted clicks alone: an owner's size is never reset (a Reset gives "
               "the defaults); a size no click lands on is said by its difference")
    place = (f"its place: back to the start's from {run}'s edges at the start size (the frame pushed to its far corner "
             "from wherever it is and brought back in Standard's step to the start line's place, each landing registered "
             "and checked)" if edges else
             f"its place: {run} measured no edges at the start size: its place is checked at the finish, not brought "
             "back")
    if edges and centre:
        place += "; its start place is the grid's centre, which the centre stop reaches at any size"
    sets = [afreg_run.step_name(k, w) for k, w in F.setup_steps(False, False, "Standard", None, True)]
    return [f"{box}: back to the start of {run}, {to}, as {run} began it ({start.get('context')!r}; run {a.run})",
            f"  {way}",
            f"  {place}",
            f"set through the menu first: {'; '.join(sets)}; the start file put back at the end puts them back (a box's "
            "size and place are in no settings file: the restore leaves them where they are put)",
            f"the box's records: width {recs['width']}, height {recs['height']}, defaults {recs['default_width']}, "
            f"{recs['default_height']}"]


def put_back_main(a) -> int:
    """--put-back RUN: RUN's start (its boxsize.jsonl's start line) and its edges at the start size (edges.jsonl's line
    "at": "start"), in a session of its own: the setup as an edges run's, the box chosen, its size brought back
    (Sizes.put_back), then its place (Sizes.finish)."""
    from camkit.frames import eyes_from_config
    from camkit.runs import Run
    from prove_run import Failed, to_shooting
    from runner import load_scan, prover_session
    start, edges = put_back_source(a.put_back)
    box = start["box"]
    doc, table = read_definition(), custom_table()
    recs = box_records(doc, box, table)
    labels, axes, r, _, t = session_parts(argparse.Namespace(tracking=False), doc, box)
    index = {s["key"]: s for s in doc.get("settings") or []}
    cycle, model = load_scan(a.scan)
    run = Run(a.run)
    hdmi = eyes_from_config(run)
    tag = {"context": start.get("context"), "source": a.put_back}
    ok = False
    with prover_session(run, hdmi, may_open={F.MEMORY_ROW}, show=0, expected=frozenset(F.EXPECTED_LEFT),
                        end_why="the settings download after the put-back") as s:
        try:
            from camkit import camset
            code, _ = aspect_of(index, camset.read(s.start))
            tag["setup"] = F.prepare(s.cam, s.link, hdmi, run, cycle, model, False, False, s.start, "Standard", index,
                                     None, circ=True)
            sw = Sizes(s.cam, s.link, hdmi, run, cycle, model, a, t, r, labels, axes, recs, rule_of(table), tag, index,
                       code)
            sw.start_travel = target_travel(edges, start)       # the place's target: the run's start line's place
            afreg_run.choose_area(s.cam, run, cycle, model, labels, axes, r, None)
            to_shooting(s.link, hdmi, "the shooting screen with the box chosen")
            try:
                ok = sw.put_back(start)
            except Failed as e:
                print(f"  stopped: {e}", flush=True)
            ok = sw.finish() and ok
        except BaseException as e:
            say_trace(e)
            raise
    return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--box", default=None, help="Custom 1, Custom 2 or Custom 3")
    ap.add_argument("--probe", choices=sorted(DIALS), default=None,
                    help="the smallest try: --clicks single clicks of this dial up and back, each registered")
    ap.add_argument("--clicks", type=int, default=PROBE_CLICKS, help=f"--probe's clicks each way (default {PROBE_CLICKS})")
    ap.add_argument("--dials", default="rear_l,front", help="the dials to walk to their ends, comma-separated")
    ap.add_argument("--block", type=int, default=BLOCK, help=f"clicks a turn toward an end (default {BLOCK})")
    ap.add_argument("--confirm", type=int, default=CONFIRM, help=f"clicks that check an end (default {CONFIRM})")
    ap.add_argument("--pattern", type=int, default=PATTERN, help=f"single clicks read from each end (default {PATTERN})")
    ap.add_argument("--edge-presses", type=int, default=F.EDGE_PRESSES, help="the presses a push toward an edge takes")
    ap.add_argument("--tracking", action="store_true", help="at the odd size, read the box in use with Tracking chosen")
    ap.add_argument("--put-back", default=None, metavar="RUN", help="bring the box back to RUN's start size and place")
    ap.add_argument("--run", default=None, help="the run's folder (default kit2_boxsize, kit2_boxsize_putback)")
    ap.add_argument("--list", action="store_true", help="print the plan only; no camera")
    add_scan_argument(ap, default=LATEST_SCAN, mode="Stills")
    add_allow_argument(ap)
    a = ap.parse_args(argv)
    a.grip = None
    a.run = a.run or ("kit2_boxsize_putback" if a.put_back else "kit2_boxsize")
    a.dials = [d.strip() for d in a.dials.split(",") if d.strip()]
    bad = [d for d in a.dials if d not in DIALS] + ([] if 1 <= a.clicks <= 10 else ["--clicks"]) + \
        ([] if 1 <= a.block <= 99 and 1 <= a.confirm <= 5 and 2 <= a.pattern <= 12 else ["--block/--confirm/--pattern"])
    if bad or not a.dials:
        sys.exit(f"boxsize_run: {bad or '--dials'}: dials are {', '.join(DIALS)}; --clicks 1-10, --block 1-99, "
                 "--confirm 1-5, --pattern 2-12")
    words = memory_allowed(a.allow) and set_allowed(a.allow)
    if not a.list and not words:
        sys.exit(f"boxsize_run: a camera run needs the owner's two words: --allow {F.MEMORY_ROW!r} (slot 1 registered "
                 f"at each size) and --allow {SET_WORD!r} (SET opens the box's editor, and OK in it keeps the size); "
                 f"--allow {RESET_WORD!r} besides lets the editor's Reset put back a default size the clicks cannot")
    others = [x for x in a.allow if not memory_allowed([x]) and not set_allowed([x]) and not reset_allowed([x])]
    if others:
        sys.exit(f"boxsize_run: --allow names {others}: this run is allowed nothing but {F.MEMORY_ROW!r}, {SET_WORD!r} "
                 f"and {RESET_WORD!r}")
    a.reset = reset_allowed(a.allow)
    if a.put_back:
        # the plan from RUN's own files and the definition alone; --list ends here, before anything reaches the camera
        start, edges = put_back_source(a.put_back)
        doc = read_definition()
        recs = box_records(doc, start["box"], custom_table())
        index = {s["key"]: s for s in doc.get("settings") or []}
        target = target_travel(edges, start)
        centre = bool(target) and F.at_centre((target.get("values") or {}).get("base") or {}, index)
        print("\n".join(put_back_plan_lines(a, start, edges, recs, centre)), flush=True)
        why = owed_refusal(start["box"], a.put_back)
    else:
        if a.box not in BOXES:
            sys.exit(f"boxsize_run: --box {a.box!r} is none of Custom 1, Custom 2 or Custom 3")
        doc, table = read_definition(), custom_table()
        recs = box_records(doc, a.box, table)
        print("\n".join(plan_lines(a, recs)), flush=True)
        why = owed_refusal(a.box)
    if a.list:
        if why:
            print(f"a camera run is refused: {why}", flush=True)
        return 0
    if why:
        sys.exit(f"boxsize_run: {why}")
    if a.put_back:
        allowed_or_exit(a.allow)
        return put_back_main(a)
    return prove(a, doc, recs, table, allowed_or_exit(a.allow))


if __name__ == "__main__":
    sys.exit(main())
