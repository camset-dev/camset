"""Prove AF Area Registration's records: each Focus Area option chosen in the menu, then Fn held on the shooting screen,
which registers it ("Registered the focus area.") into the Registered AF area records (2026-11-09).

    .venv/bin/python -u kit/provers/afreg_run.py --areas missing --list
    .venv/bin/python -u kit/provers/afreg_run.py --allow "Fn hold on the shooting screen" --areas missing [--limit N]
    .venv/bin/python -u kit/provers/afreg_run.py --allow "Fn hold on the shooting screen" --areas "Spot: S,Tracking: Custom 2"
    .venv/bin/python -u kit/provers/afreg_run.py --allow "Fn hold on the shooting screen" --areas missing --grip down
    .venv/bin/python -u kit/provers/afreg_run.py --proved                           (the codes the run's lines proved)

--allow "Fn hold on the shooting screen" (FN_HOLD) is the owner's word for the hold: held on the shooting screen with
AF Area Registration On, Fn registers the area, a registration of the kind the playbook's rule 2 names, and the kit
presses no key there but MENU unless a run names it (docs/decisions/0021). A camera run refuses to start without it,
and with any other --allow; every proof line carries it ("allowance", runner.allowed_or_exit). --list and --proved
touch no camera and need none.

The camera (the a1 II, firmware 4.00; runs/<model>_fw<fw>/kit2_afreg, 2026-11-02, did five of them by hand): with
AF Area Registration On, holding Fn on the shooting screen copies the orientation's live Focus Area memories into the
"Registered AF area" records: its kind, its area (the 24 Focus Area options, numbered as the live memory 0x0f46) and,
for a Tracking option, its start area in two numberings; with Switch V/H AF Area Off one hold writes all three
orientations' copies. The a1 II's hand tables (data/ILCE-1M2_fw4.00/hand_tables_ILCE-1M2_fw4.00.json: their
FRAME_PROOFS and NEW_RECORDS entries, and RECORD_FIXES) name them and their values.

--areas: labels as the definition names the area record's values ("Spot: S", "Tracking: Custom 2"), comma-separated;
"missing", the values the area record's proofs have not covered; or "all". --list prints the plan and the codes each
hold must write, and touches no camera. --proved prints the codes the run's applied lines proved, record by record,
for the REG table.

A run is bracketed as every run is (decision 15; runner.prover_session): the start download, then the setup through
the menu, each row set as kit/provers/mode_switch.py's --set sets one (set_row): AF Area Registration = On, Switch V/H
AF Area = Off (grip: AF Point + AF Area), and, when the plan holds a Tracking option (Focus Area offers Tracking under
Continuous AF only: the carousel under Single-shot AF has no Tracking), Mode Dial Control Set's Drive Mode Dial = Set
with Menu, then Drive Mode = Single Shooting (Continuous AF is refused under some drive modes: the camera says so in a
notice when the Focus Mode row is set, so the prover sets Drive Mode to Single Shooting through the menu first and the
restore puts the file's own back; --drive-mode auto|menu|leave), Mode Dial Control Set's Focus Mode Dial = Set with
Menu, then Focus Mode = Continuous AF. A step whose OK is answered by a "not available as follows" notice fails the
setup (the notice closed with its OK first): the console says a notice refused the step and names its frame, and the
notice's words go to the run's events.jsonl only, as a notice can name another setting's value, the camera's own
(decision 16). A download after the setup is kept in setup.jsonl with what it changed. The start file put back at the
end restores the two dials and the drive mode with the rest.
Then per area: MENU, Focus Area by the page scan, the carousel's option (Down/Up, each step read) and its second axis
(Right/Left: the Spot sizes, Custom 1-3, the Tracking areas; kit2_axes/axes.json's values), OK, which closes the menu;
a download (before-<area>), the menu lock's wait, Fn held 1500 ms on the shooting screen (Link.press with Fn allowed:
safety.GUARDED_INPUTS), the message's wait, a download (after-<area>), the diff, and one proof line in the run's
proofs.jsonl, the run marked as one of the camera's proof runs (camkit.runs.PROOF_RUN), which kit/pass2_report.py reads
beside the main run:
    {"path": [MENU], "kind": "list", "index": <the area's code>, "label": <the area>, "via", "dat", "base",
     "expected": [{"key", "value"}], "changes": <the registered records' changes>, "side_effects": [keys],
     "applied": <the area record moved to the area's code and every expected record holds its code>, "not_applied"}
tagged with the context ("Switch V/H AF Area Off", and --context). A hold that changed nothing is recorded not applied,
never as a proof. A non-Tracking option's hold also copies the live Tracking start area, the camera's own setting and no
code of that option: those records are side effects, kept by key only (the downloads hold them), named whether the copy
changed them or not, so the report never credits what they held to the area (pass2_report.side_named); so is any other
record the hold changed that the plan does not expect. At the end the start
file goes back on and is checked (exit EXIT_UNRESTORED when it did not take), which also puts the setup back.

Nothing the start file holds is printed (decision 16): the plan, each area registered and the codes it wrote, and the
count of records that differ at the end. One trace: when the registration already holds the plan's first area, that
area is registered last (its hold could show no change first), or, alone, after one other area.

--grip down|up: the owner holds the camera vertically for the whole run (orient_run.py's plumbing): Switch V/H AF Area
= AF Point + AF Area, so a hold writes that orientation's copies alone; the turned Focus Area dialog is read upright
(orient_run.open_row and step_to), the context says the grip, and "missing" reads that orientation's area record.
Not tried on the camera: whether the setup's lists stay level as the menu pages do (orient_run's note: menus stay
level, dialogs turn); a list read turned fails the setup and the run restores.
"""
import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parent))
from camkit import definitions, jsonl, match, paths, safety  # noqa: E402
from runner import LATEST_SCAN, add_allow_argument, add_scan_argument, allowed_or_exit, read_json  # noqa: E402

MENU = "AF Area Registration On, Fn held on the shooting screen"   # the proofs' row: the REG table's menu
ROW = "Focus Area"
REG_ROW, VH_ROW, FOCUS_ROW, DIAL_ROW = "AF Area Registration", "Switch V/H AF Area", "Focus Mode", "Mode Dial Control Set"
FOCUS_DIAL, BY_MENU, CONTINUOUS = "Focus Mode Dial", "Set with Menu", "Continuous AF"
DRIVE_ROW, DRIVE_DIAL, SINGLE = "Drive Mode", "Drive Mode Dial", "Single Shooting"
HOLD_MS = 1500
MESSAGE_S = 2.5          # "Registered the focus area." is gone 1.5-3 s after the hold (kit2_afreg 00029-00031)
ORIENTATIONS = {None: "horizontal", "down": "vertical, grip down", "up": "vertical, grip up"}
VH = {None: "Off", "down": "AF Point + AF Area", "up": "AF Point + AF Area"}
PARTS = ("area", "kind", "Tracking start area", "Tracking start area, alt numbering")
NAME = "Registered AF area: {part} ({orientation})"            # their names in the hand tables (RECORD_FIXES, NEW_RECORDS)
# the owner's word for the hold, given per run as --allow: Fn held on the shooting screen with AF Area Registration On
# registers the area (a registration: the playbook's rule 2), a press the kit makes there only when named (decision 21)
FN_HOLD = "Fn hold on the shooting screen"


# ---------------------------------------------------------------- the plan, from the definition (no camera)

def records(doc: dict, orientation: str) -> dict:
    """{part: the definition's setting} of one orientation's Registered AF area records, by the REG table's names; a
    definition without the area record cannot plan."""
    by_name = {s["name"]: s for s in doc.get("settings") or []}
    out = {p: by_name[n] for p in PARTS if (n := NAME.format(part=p, orientation=orientation)) in by_name}
    if "area" not in out:
        sys.exit(f"afreg_run: the definition has no {NAME.format(part='area', orientation=orientation)!r}")
    return out


def bare(label) -> str:
    """A label compared without case, spaces or colons ("Tracking: Spot S", "tracking spot s" and the axis walk's
    "Tracking: SpotS" alike)."""
    return re.sub(r"[\s:]+", "", match.key(label))


def kind_of(label: str) -> str:
    """The kind record's label for an area: Tracking, Spot, Custom, or the area itself (Wide, Zone, ...)."""
    if label.startswith("Tracking:"):
        return "Tracking"
    if label.startswith("Spot:"):
        return "Spot"
    return "Custom" if re.fullmatch(r"Custom \d", label) else label


def start_of(label: str) -> str | None:
    """A Tracking area's start area as the start records label it ("Tracking: Spot S" -> "Spot: S"); None for any
    other area, whose hold copies the live Tracking start area, no code of its own."""
    if not label.startswith("Tracking:"):
        return None
    sub = label.split(":", 1)[1].strip()
    return f"Spot: {sub[5:]}" if sub.startswith("Spot ") else sub


def code_of(setting: dict, label: str) -> int | None:
    hits = [v for v, lab in setting.get("values") or [] if bare(lab) == bare(label)]
    return hits[0] if len(hits) == 1 else None


def plan(doc: dict, areas: str, grip: str | None = None) -> list:
    """[{"label", "code", "expected": {key: code}, "copied", "own_key", "other_area_keys"}] for the areas asked for, in the area
    record's order: "missing", its values not in its proved.values; "all"; else the labels given. Level (no grip), with
    Switch V/H AF Area Off, a hold writes all three orientations, so each one's records are expected; with a grip, that
    orientation's alone. copied: a non-Tracking area's Tracking start area records of those orientations, which its
    hold copies from the live start area (the camera's own setting): side effects, whatever they hold after. own_key is
    the area record of the orientation the plan reads ("missing" too); other_area_keys the area records of the
    orientations not expected (judge names one that moved instead)."""
    orientation = ORIENTATIONS[grip]
    own = records(doc, orientation)["area"]
    values = [(v, lab) for v, lab in own.get("values") or []]
    if areas == "all":
        chosen = values
    elif areas == "missing":
        done = set((own.get("proved") or {}).get("values") or ())
        chosen = [x for x in values if x[0] not in done]
    else:
        asked = [x.strip() for x in areas.split(",") if x.strip()]
        unknown = [x for x in asked if not any(bare(lab) == bare(x) for _, lab in values)]
        if unknown or not asked:
            sys.exit(f"afreg_run: --areas {areas!r}: {unknown or 'nothing'} not among {[lab for _, lab in values]}")
        chosen = [x for x in values if any(bare(x[1]) == bare(a) for a in asked)]
    every = {o: records(doc, o) for o in ([orientation] if grip else ORIENTATIONS.values())}
    names = {s["name"]: s["key"] for s in doc.get("settings") or []}
    others = [k for o in ORIENTATIONS.values() if o not in every
              and (k := names.get(NAME.format(part="area", orientation=o)))]
    out = []
    for code, label in chosen:
        expected, copied = {}, []
        for recs in every.values():
            for part, s in recs.items():
                lab = {"area": label, "kind": kind_of(label)}.get(part) or start_of(label)
                if lab is None:
                    copied.append(s["key"])     # a non-Tracking area's start: the live one, copied (a side effect)
                    continue
                c = code_of(s, lab)
                if c is None:
                    sys.exit(f"afreg_run: {s['name']} has no value {lab!r} (for {label!r})")
                expected[s["key"]] = c
        out.append({"label": label, "code": code, "expected": expected, "copied": sorted(copied),
                    "own_key": own["key"], "other_area_keys": others})
    return out


def ordered(todo: list, held, every: list) -> list:
    """The plan with its first area put last when the registration already holds it (`held`, the area record's value
    after the setup), since its hold could show no change; a plan of that one area alone gets another area first
    (the first non-Tracking one of `every`, which needs no Focus Mode). Nothing is said: the order is the trace."""
    if not todo or todo[0]["code"] != held:
        return list(todo)
    if len(todo) > 1:
        return todo[1:] + todo[:1]
    other = next(t for t in every if t["code"] != held and not t["label"].startswith("Tracking"))
    return [other] + list(todo)


def judge(t: dict, changes: list, after: dict) -> tuple:
    """(the changes credited to the area, the side effects (keys only: the other records that changed, and the start
    area copies the plan names, changed or not), applied, why not). Applied: the plan's own area record moved to the
    area's code, and every expected record holds its code after the hold. A hold that changed nothing is never applied.
    `changes`: [{"key", "before", "after"}]; `after`: {key: value} of the expected records in the download after the
    hold."""
    moved = {c["key"]: c for c in changes}
    credited = [c for c in changes if c["key"] in t["expected"]]
    side = sorted({k for k in moved if k not in t["expected"]} | set(t.get("copied") or ()))
    wrong = sorted(k for k, v in t["expected"].items() if after.get(k) != v)
    own = moved.get(t["own_key"])
    why = None
    if not changes:
        why = "nothing changed: the hold registered nothing"
    elif own is None or own["after"] != t["code"]:
        why = f"{t['own_key']} did not move to {t['code']}"
        swapped = [k for k in t.get("other_area_keys") or () if k in moved and moved[k]["after"] == t["code"]]
        if swapped:
            why += f" ({', '.join(swapped)} did: the copy written is not the one the definition names)"
    elif wrong:
        why = f"not on the expected code after the hold: {', '.join(wrong)}"
    return credited, side, why is None, why


def context_of(grip: str | None, extra: str | None) -> str:
    base = f"Switch V/H AF Area = AF Point + AF Area, camera grip {grip}" if grip else "Switch V/H AF Area Off"
    return f"{base}, {extra}" if extra else base


def setup_rows(grip: str | None, focus: bool) -> list:
    """[(path, option)] the run sets through the menu after the Focus Mode Dial (focus), in order."""
    rows = [([FOCUS_ROW], CONTINUOUS)] if focus else []
    return rows + [([REG_ROW], "On"), ([VH_ROW], VH[grip])]


def setup_steps(grip: str | None, focus: bool, drive: bool) -> list:
    """[(kind, text)] the whole setup in order: kind "dial" (a Mode Dial Control Set cell put on Set with Menu; text is
    the cell), "drive" (Drive Mode's carousel on Single Shooting) or "row" (a list row, set_row; text is its
    "path = option")."""
    steps = []
    if drive:
        steps += [("dial", DRIVE_DIAL), ("drive", f"{DRIVE_ROW} = {SINGLE}")]
    if focus:
        steps.append(("dial", FOCUS_DIAL))
    return steps + [("row", f"{' > '.join(p)} = {o}") for p, o in setup_rows(grip, focus)]


def step_name(kind: str, what: str) -> str:
    return f"{DIAL_ROW} / {what} = {BY_MENU}" if kind == "dial" else what


def proof_line(t: dict, got: dict, hold: dict, base: Path, dat: Path, changes: list, after: dict,
               grip: str | None, setup: list) -> dict:
    credited, side, applied, why = judge(t, changes, after)
    return {"path": [MENU], "menu": MENU, "kind": "list", "index": t["code"], "label": t["label"],
            "via": f"Focus Area = {t['label']} chosen in the menu, then Fn held {HOLD_MS} ms on the shooting screen",
            "shown": got["shown"], "vlm": got["vlm"], **{k: got[k] for k in ("read_by", "cell_readings") if k in got},
            "chosen_frame": got["chosen_frame"], "row_frame": got["row_frame"],
            "hold_frames": hold["frames"], "said": hold["said"], "dat": dat.name, "base": base.name,
            "expected": [{"key": k, "value": v} for k, v in t["expected"].items()], "changes": credited,
            "side_effects": side, "applied": applied, **({"not_applied": why} if why else {}), "setup": setup,
            **({"upright": True, "grip": grip} if grip else {})}


def proved_codes(lines: list) -> dict:
    """{record key: sorted codes} the applied lines proved (their expected codes, never a value from before)."""
    out = {}
    for r in lines:
        if r.get("path") == [MENU] and r.get("applied") is True:
            for e in r.get("expected") or []:
                out.setdefault(e["key"], set()).add(e["value"])
    return {k: sorted(v) for k, v in sorted(out.items())}


def hold_allowed(allow) -> bool:
    """Whether a run's --allow words name the Fn hold (FN_HOLD; compared as safety.named compares a row's name)."""
    return safety.named(FN_HOLD, allow)


def slug(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "-", label).strip("-").lower()


# ---------------------------------------------------------------- the camera

def route(label: str, labels: list, axes: dict) -> tuple | None:
    """(carousel index, axis option or None, axis value index or None) of an area, by pass 1's map of the carousel
    and the axis walk's values (orient_run.which); None when they do not name it once."""
    from orient_run import axis_of, which
    w = which(label, labels, axes)
    if w is None:
        return None
    i, v = w
    return i, (axis_of(labels[i], axes) if v is not None else None), v


def main_of(reading: str, labels: list, axes: dict) -> int | None:
    """The carousel option a reading of its title names: exactly (orient_run.which), else the one label or axis value
    it starts with (an icon read after it: "Custom 3 7"), else the one label of its name before the colon (a size OCR
    garbled: "Spot: XI", "Tracking: Spot ?"), else the one option whose axis values all begin as the reading does
    (the value's digit lost under the frame's corner: "Customß 7" is the Custom option, whichever of its three)."""
    from orient_run import axis_of, which
    from proving.screens import main_name, option_key
    if not reading:
        return None
    w = which(reading, labels, axes)
    if w is not None:
        return w[0]
    k = option_key(reading)
    names = [axes[o]["values"] if (o := axis_of(lab, axes)) else [lab] for lab in labels]
    hits = {i for i, vals in enumerate(names) if any(k.startswith(option_key(v)) for v in vals)}
    if len(hits) != 1:
        hits = {i for i, lab in enumerate(labels) if ":" in lab and ":" in reading
                and option_key(main_name(lab, "dialog")) == option_key(main_name(reading, "dialog"))}
    if len(hits) != 1:
        # the title overdrawn by the frame's own corner ("Customß 7": the Custom 3 box's corner over the title, with the
        # stand-in reader answering the lit cell alone, "C3"; kit2_framepos 01244_reread.png, 2026-11-09): the one
        # option whose name, or whose axis values' common lead of three characters or more, the reading starts with
        leads = [os.path.commonprefix([option_key(v) for v in vals]) for vals in names]
        hits = {i for i, lead in enumerate(leads) if len(lead) >= 3 and k.startswith(lead)}
    return next(iter(hits)) if len(hits) == 1 else None


def main_at(cam, labels: list, axes: dict) -> int | None:
    """The carousel option under the cursor: the title read once it has redrawn (it follows the strip), else the
    vision reader's reading (the owner's rule: ask the reader before failing)."""
    from proving.screens import carousel_text, vlm_option
    time.sleep(0.4)
    cam.refresh("reread")
    i = main_of(carousel_text(cam), labels, axes)
    return i if i is not None else main_of(vlm_option(cam), labels, axes)


def choose_level(cam, cycle, model, labels, axes, i, o, v) -> dict:
    """The camera level: MENU, Focus Area by the scan, Right; the carousel's option i (Down/Up the short way, every
    step read, so a carousel one shorter under Single-shot AF still comes round), then axis value v (Right/Left, each
    step read: prove_run.axis_reading). Returns how the axis value was read at the end ({} from the title, or an
    option without an axis; the strip's lit cell says so: {"read_by": "axis cell", ...})."""
    from camkit import ocr
    from mode_switch import find, open_menu
    from prove_run import Failed, axis_reading
    open_menu(cam)
    find(cam, cycle, model, ROW)
    cam.press("right")
    head = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 50))
    if cam.read().kind != "dialog" or "focus area" not in head.lower():
        raise Failed(f"Right on {ROW} opened {cam.read().kind} ({head!r}, {cam.frame.path.name})")
    n = len(labels)
    for _ in range(2 * n + 1):
        cur = main_at(cam, labels, axes)
        if cur == i:
            break
        if cur is None:
            raise Failed(f"{ROW}: which option the carousel is on could not be read ({cam.frame.path.name})")
        d = (i - cur) % n
        cam.press("down" if d <= n - d else "up")
        if cam.read().kind != "dialog":
            raise Failed(f"{ROW}: the carousel closed ({cam.read().kind}, {cam.frame.path.name})")
    else:
        raise Failed(f"{ROW}: {labels[i]!r} never came under the cursor (Focus Area Limit, or no Tracking under "
                     "Single-shot AF?)")
    if o is None:
        return {}
    vals = axes[o]["values"]
    m = len(vals)
    for _ in range(m + 2):
        cur, how = axis_reading(cam, vals)
        if cur == v:
            return how
        if cur is None:
            raise Failed(f"{ROW} / {o}: the axis value could not be read ({cam.frame.path.name})")
        d = (v - cur) % m
        cam.press("right" if d <= m - d else "left")
        if cam.read().kind != "dialog":
            raise Failed(f"{ROW} / {o}: the carousel closed ({cam.read().kind}, {cam.frame.path.name})")
    raise Failed(f"{ROW} / {o}: {vals[v]!r} never came up (Focus Area Limit?)")


def choose_area(cam, run, cycle, model, labels, axes, r: tuple, grip: str | None) -> dict:
    """The area under the carousel's cursor (level, or turned and read upright with a grip: orient_run's open_row and
    step_to), checked for a confirmation, read by the second reader, OK. The menu closes on OK (kit2_afreg 00024)."""
    from camkit import ocr
    from prove_run import Failed
    from proving.screens import carousel_text, vlm_option
    i, o, v = r
    how = {}                                    # how the axis value was read, when the strip's lit cell read it
    if grip:
        from orient_run import GRIPS, open_row, reading, step_to, upright
        k, shots = GRIPS[grip], run.dir / "upright"
        open_row(cam, cycle, model, ROW, k, shots)
        step_to(cam, k, shots, labels, axes, "up", lambda w: w is not None and w[0] == i, len(labels),
                f"{ROW}: {labels[i]!r}")
        if v is not None:
            step_to(cam, k, shots, labels, axes, "right", lambda w: w == (i, v), len(axes[o]["values"]),
                    f"{ROW}: {axes[o]['values'][v]!r}")
        shown = reading(cam, k, shots)[1]
        full = ocr.text_in(upright(cam, k, shots), (0, 0, 480, 640))
    else:
        how = choose_level(cam, cycle, model, labels, axes, i, o, v)
        shown = carousel_text(cam)
        full = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
    if safety.confirmation(full):
        raise Failed(f"{ROW}: the dialog reads like a confirmation ({safety.confirmation(full)}): no OK")
    chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)
    cam.press("enter")
    if cam.read().kind == "notice":
        said = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
        step = f"{ROW} = {axes[o]['values'][v] if v is not None else labels[i]}"
        name = kept_notice(cam, step, said, "area_notice")
        cam.press("menu")
        raise Failed(f"a notice refused {step} ({name}; its words are in the run's events.jsonl)")
    return {"shown": shown, "vlm": seen_vlm, "chosen_frame": chosen, "row_frame": cam.frame.path.name, **how}


def dial_cell(name: str = FOCUS_DIAL) -> list:
    """The `name` cell (Focus Mode Dial, Drive Mode Dial) of Mode Dial Control Set's table, as the table walk found it
    (kit2_tables)."""
    from prove_run import Failed
    from proving.base import TABLES
    try:
        cells = read_json(TABLES)[DIAL_ROW]["cells"]
    except (OSError, ValueError, KeyError) as e:
        raise Failed(f"{DIAL_ROW} is not in the table walk ({TABLES}): kit/table_walk.py --rows '{DIAL_ROW}' first "
                     f"({type(e).__name__})") from None
    hit = [c["pos"] for c in cells if match.key(c.get("row_label")) == match.key(name)]
    if len(hit) != 1:
        raise Failed(f"{DIAL_ROW}: the table walk has no one {name!r} cell")
    return hit[0]


def focus_dial_by_menu(cam, cycle, model, dial: str = FOCUS_DIAL):
    """Mode Dial Control Set's `dial` cell = Set with Menu, so Focus Mode (or Drive Mode) is the menu's (the a1 II's
    focus mode and drive mode are dials). Right on the row (a note about the setting first, its OK leading on, as mode_switch.dial_by_menu takes
    it; a first-time note's OK without its tick box: first_time_notice), the table, the Focus Mode Dial cell
    (proving.tables.to_cell, its name read under the picture), Enter, Set with Menu, OK: the table takes it at once
    (table_walk: commit "menu"). The Set All buttons are never pressed."""
    from camkit import ocr
    from mode_switch import find, text
    from prove_run import Failed
    from proving.screens import bar_text, first_time_notice, option_key
    from proving.tables import to_cell
    cell = dial_cell(dial)
    find(cam, cycle, model, DIAL_ROW)
    cam.press("right")
    for _ in range(3):
        t = text(cam)
        if cam.read().kind == "table" and re.search(r"set\s*all\s*with", t, re.I):
            break
        if first_time_notice(cam):
            continue
        if cam.read().kind == "list" or not re.search(r"mode dial", t, re.I) or safety.confirmation(t):
            name = kept_notice(cam, f"Right on {DIAL_ROW}", t, "dial_screen")
            raise Failed(f"Right on {DIAL_ROW!r} opened {cam.read().kind} ({name}; what it showed is in the run's "
                         "events.jsonl)")
        cam.press("enter")                      # the note's OK
    else:
        raise Failed(f"{DIAL_ROW}: its table did not come ({cam.read().kind}, {cam.frame.path.name})")
    to_cell(cam, cell)
    name = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (380, 320, 640, 370))
    if cam.read().focus != "cell" or match.key(dial) not in match.key(name):
        raise Failed(f"{DIAL_ROW}: the lit cell is not the {dial} ({name!r}, {cam.frame.path.name})")
    if safety.confirmation(text(cam)):
        raise Failed(f"{DIAL_ROW}: the table reads like a confirmation ({cam.frame.path.name})")
    cam.press("enter")
    if cam.read().kind != "list":
        raise Failed(f"{DIAL_ROW} / {dial}: Enter opened {cam.read().kind}, not its list ({cam.frame.path.name})")
    for _ in range(4):
        if option_key(match.clean(bar_text(cam))) == option_key(BY_MENU):
            break
        cam.press("down")
    else:
        raise Failed(f"{DIAL_ROW} / {dial}: {BY_MENU!r} is not in its list ({cam.frame.path.name})")
    print(f"{DIAL_ROW} / {dial}: choosing {BY_MENU!r}", flush=True)
    cam.press("enter")
    if cam.read().kind != "table":
        raise Failed(f"{DIAL_ROW}: after OK the screen is {cam.read().kind}, not the table ({cam.frame.path.name})")


def scrub(msg: str) -> str:
    """A failure as printed: without the list's lit option (set_row's "(on '...')"), which can be the held one."""
    return re.sub(r"\s*\(on '.*?'\)", "", msg)


def kept_notice(cam, step: str, words: str | None = None, kind: str = "setup_notice") -> str:
    """The notice (or screen) on the camera kept in the run's events.jsonl (`kind`: the step, the frame, its words, read
    from the screen unless given), never printed nor put in a failure's message, which a run's jsonl stores: a notice
    can name another setting's value, the camera's own (decision 16). Returns the frame's name."""
    from mode_switch import text
    name = cam.frame.path.name
    cam.run.log(kind, step=step, frame=name, notice=" ".join((text(cam) if words is None else words).split()))
    return name


def refused_by_notice(cam, say, step: str):
    """A `say` for set_row (it calls it with "   notice after OK (...)" before closing the notice with MENU): the notice's
    words are kept (kept_notice) and never said; when it is "not available as follows", it is closed with its OK and
    the step fails, the message naming the step and the notice's frame only."""
    from mode_switch import text
    from prove_run import Failed

    def watch(msg: str):
        if "notice after OK" not in msg:
            say(msg)
            return
        t = text(cam)
        refused = re.search(r"not\s+available\s+as\s+follows", t, re.I)
        name = kept_notice(cam, step, t)
        if refused:
            if safety.confirmation(t):          # never Enter on a confirmation (camkit.safety)
                raise Failed(f"a notice after {step} reads like a confirmation ({name}): no Enter; the setup stops "
                             "here and the start file goes back")
            cam.press("enter")
            raise Failed(f"a notice refused {step} ({name}; its words are in the run's events.jsonl): the setup stops "
                         "here and the start file goes back")
        say(f"   a notice after OK ({name}), closed with MENU; its words are in the run's events.jsonl")
    return watch


def set_setup_row(cam, cycle, model, path: list, option: str):
    """A setup row put on its option (mode_switch.set_row) with refused_by_notice watching; a failure said without the
    list's lit option (scrub)."""
    from mode_switch import set_row
    from prove_run import Failed
    step = f"{' > '.join(path)} = {option}"
    try:
        set_row(cam, cycle, model, path, option, refused_by_notice(cam, lambda m: print(m, flush=True), step))
    except Failed as e:
        raise Failed(scrub(str(e))) from None


def drive_single(cam, cycle, model):
    """Drive Mode = Single Shooting: the row's carousel (Enter, as bracket_run opens it), Up/Down the short way to
    the option, every step read (carousel_text, the vision reader when it is blank), OK. A notice after OK closes with
    its OK and fails the step, its words kept in the run's events.jsonl (kept_notice), never printed."""
    from camkit import ocr
    from mode_switch import find, text
    from pass3_run import labels_of
    from prove_run import Failed
    from proving.screens import carousel_text, main_name, option_key, vlm_option
    labels, kind = labels_of([DRIVE_ROW])
    names = [main_name(lab, "dialog") for lab in labels]
    if kind != "dialog" or option_key(SINGLE) not in map(option_key, names):
        raise Failed(f"{DRIVE_ROW}: pass 1's map has no {SINGLE!r} carousel option ({kind})")
    want, n = [option_key(x) for x in names].index(option_key(SINGLE)), len(names)
    find(cam, cycle, model, DRIVE_ROW)
    cam.press("enter")
    head = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 60)).lower()
    if cam.read().kind != "dialog" or "drive mode" not in head:
        raise Failed(f"Enter on {DRIVE_ROW} opened {cam.read().kind} ({cam.frame.path.name}): {head[:60]!r}")
    for _ in range(n + 2):
        time.sleep(0.4)
        cam.refresh("reread")
        hit = []
        for read in (lambda: carousel_text(cam), lambda: vlm_option(cam)):
            k = option_key(main_name(read(), "dialog"))
            hit = [i for i, x in enumerate(names) if k and option_key(x) == k]
            if len(hit) == 1:
                break
        else:
            raise Failed(f"{DRIVE_ROW}: which option the carousel is on could not be read ({cam.frame.path.name})")
        if hit[0] == want:
            break
        d = (want - hit[0]) % n
        cam.press("down" if d <= n - d else "up")
        if cam.read().kind != "dialog":
            raise Failed(f"{DRIVE_ROW}: the carousel closed ({cam.read().kind}, {cam.frame.path.name})")
    else:
        raise Failed(f"{DRIVE_ROW}: {SINGLE!r} never came under the cursor ({cam.frame.path.name})")
    if safety.confirmation(text(cam)):
        raise Failed(f"{DRIVE_ROW}: the dialog reads like a confirmation: no OK ({cam.frame.path.name})")
    print(f"{DRIVE_ROW}: choosing {SINGLE!r}", flush=True)
    cam.press("enter")
    if cam.read().kind == "notice":
        t = text(cam)
        name = kept_notice(cam, f"{DRIVE_ROW} = {SINGLE}", t)
        if safety.confirmation(t):              # never Enter on a confirmation (camkit.safety)
            raise Failed(f"a notice after {DRIVE_ROW} = {SINGLE} reads like a confirmation ({name}): no Enter; the "
                         "setup stops here and the start file goes back")
        cam.press("enter")                      # the notice's OK
        raise Failed(f"a notice refused {DRIVE_ROW} = {SINGLE} ({name}; its words are in the run's events.jsonl): the "
                     "setup stops here and the start file goes back")


def prepare(cam, link, hdmi, run, cycle, model, grip, focus: bool, drive: bool, start: Path) -> tuple:
    """The setup through the menu (setup_steps: the Drive Mode Dial and Drive Mode when `drive`, then the Focus Mode
    Dial when `focus`, then the rows), then a download kept in setup.jsonl with the keys it changed; returns (that
    download, the steps). The count only is printed."""
    from camkit import camset
    from mode_switch import open_menu
    from prove_run import LOCK_S, to_shooting
    from runner import close_screen
    steps = []
    rows = {f"{' > '.join(p)} = {o}": (p, o) for p, o in setup_rows(grip, focus)}
    for kind, what in setup_steps(grip, focus, drive):
        open_menu(cam)
        if kind == "dial":
            focus_dial_by_menu(cam, cycle, model, what)
        elif kind == "drive":
            drive_single(cam, cycle, model)
        else:
            path, option = rows[what]
            set_setup_row(cam, cycle, model, path, option)
        close_screen(cam, link)
        time.sleep(1.0)
        steps.append(step_name(kind, what))
    to_shooting(link, hdmi, "the download after the setup")
    time.sleep(1)
    ref = link.download("after-setup")
    changed = [c.key for c in camset.diff(camset.read(start), camset.read(ref))]
    jsonl.append(run.dir / "setup.jsonl", {"t": round(time.time(), 3), "steps": steps, "start": start.name,
                                           "after": ref.name, "changed": changed})
    print(f"setup: {'; '.join(steps)}; {len(changed)} records now differ from the start file (the restore puts them "
          "back)", flush=True)
    time.sleep(LOCK_S)
    return ref, steps


def ready_to_hold(cam, done_at: float):
    """After a download the camera says "Saving to the connected device..." and locks the menu a moment (proving.nav
    .after_download waits so before a MENU): the same wait before the hold, then the shooting screen with no message."""
    from camkit.live import text_of
    from prove_run import LOCK_S, Failed
    time.sleep(1.0)
    while True:
        s = cam.refresh("before-hold")
        waited = time.monotonic() - done_at
        if waited > LOCK_S and s.kind == "shooting" and not re.search(r"saving", text_of(cam), re.I):
            return
        if waited > 25:
            raise Failed(f"before the hold the camera stayed on a {s.kind} screen ({cam.frame.path.name})")
        time.sleep(0.4)


def hold_fn(cam, run, grip: str | None, allowed: bool = False) -> dict:
    """Fn held HOLD_MS on the shooting screen, allowed by name (safety.GUARDED_INPUTS; Link.press marks it so for
    camlink) and named for the shooting screen (on_shooting, decision 21), only when the run was given the owner's word
    for it (allowed: --allow FN_HOLD); the frame after it and the camera's message, read upright with a grip."""
    from camkit import ocr
    from camkit.live import text_of
    from prove_run import Failed
    if not allowed:
        raise Failed(f"Fn is held on the shooting screen only with the owner's word: --allow {FN_HOLD!r}")
    if cam.read().kind != "shooting":
        raise Failed(f"not on the shooting screen before the hold ({cam.read().kind}, {cam.frame.path.name})")
    first = cam.frame.path.name
    cam.press("fn", allow=frozenset({"fn"}), hold_ms=HOLD_MS, on_shooting=frozenset({"fn"}))
    if grip:
        from orient_run import GRIPS, upright
        said = ocr.text_in(upright(cam, GRIPS[grip], run.dir / "upright"), (0, 0, 480, 640))
    else:
        said = text_of(cam)
    m = re.search(r"registered[^.\n]*\.?", said, re.I)
    return {"frames": [first, cam.frame.path.name], "said": m.group(0).strip() if m else "", "screen": cam.read().kind}


class PutOff(Exception):
    """The registration holds the area already before its hold: no change could show."""


def register(cam, link, hdmi, run, cycle, model, labels, axes, t: dict, r: tuple, grip, setup: list, out,
             allowed: bool = False) -> dict:
    """One area: chosen, a download, Fn held (allowed: the owner's word for the hold, hold_fn), a download, the diff,
    one proof line. Returns the line."""
    from camkit import camset
    from prove_run import LOCK_S, held_value, to_shooting
    from runner import changes_of
    got = choose_area(cam, run, cycle, model, labels, axes, r, grip)
    to_shooting(link, hdmi, "the download before the hold")
    time.sleep(1)
    base = link.download(f"before-{slug(t['label'])}")
    if held_value(camset.read(base), t["own_key"]) == t["code"]:
        time.sleep(LOCK_S)                      # the menu lock after a download, before the next area's MENU
        raise PutOff(t["label"])
    ready_to_hold(cam, time.monotonic())
    hold = hold_fn(cam, run, grip, allowed)
    time.sleep(MESSAGE_S)
    to_shooting(link, hdmi, "the download after the hold")
    time.sleep(1)
    dat = link.download(f"after-{slug(t['label'])}")
    after_cs = camset.read(dat)
    changes = changes_of(camset.diff(camset.read(base), after_cs))
    after = {k: held_value(after_cs, k) for k in t["expected"]}
    line = proof_line(t, got, hold, base, dat, changes, after, grip, setup)
    out.write(json.dumps(line) + "\n")
    out.flush()
    wrote = ", ".join(f"{c['key']} -> {c['after']}" for c in line["changes"]) or "nothing"
    other = f"; {len(line['side_effects'])} side effects, no code of the area ({', '.join(line['side_effects'])})" \
        if line["side_effects"] else ""
    verdict = "registered" if line["applied"] else f"NOT applied ({line['not_applied']})"
    print(f"  {t['label']} (code {t['code']}): {verdict}; wrote {wrote}{other}"
          f"{'' if hold['said'] else '; no message read'}", flush=True)
    time.sleep(LOCK_S)
    return line


def prove(a, doc: dict, todo: list, focus: bool, drive: bool, context: str, allowance: str = "") -> int:
    from camkit.frames import eyes_from_config
    from camkit.runs import Run, mark_proof_run
    from camkit import camset
    from mode_switch import MAY_OPEN
    from pass3_run import labels_of
    from prove_run import AXES, Failed, held_value
    from runner import close_screen, load_scan, proofs_file, prover_session
    labels, kind = labels_of([ROW])
    if kind != "dialog":
        sys.exit(f"{ROW} is a {kind} in pass 1's map, not a carousel")
    axes = {o: info for o, info in read_json(AXES).get(ROW, {}).items() if len(info["values"]) > 1}
    routes = {t["label"]: route(t["label"], labels, axes) for t in todo}
    lost = [lab for lab, r in routes.items() if r is None]
    if lost:
        sys.exit(f"pass 1's map and the axis walk ({AXES}) do not name {lost} once: walk the axes first "
                 "(kit/axis_walk.py --rows 'Focus Area')")
    every = plan(doc, "all", a.grip)
    routes.update({t["label"]: route(t["label"], labels, axes) for t in every if t["label"] not in routes})
    cycle, model = load_scan(a.scan)
    run = Run(a.run)
    mark_proof_run(run.dir, "kit/provers/afreg_run.py")       # the report reads its proofs beside the main run's
    if a.grip:
        (run.dir / "upright").mkdir(exist_ok=True)
    hdmi = eyes_from_config(run)
    lines = []
    with proofs_file(run, context, {"allowance": allowance} if allowance else None) as out, \
            prover_session(run, hdmi, may_open=MAY_OPEN if focus or drive else (), show=0,
                           end_why="the settings download after the registrations") as s:
        cam, link = s.cam, s.link
        ref, setup = prepare(cam, link, hdmi, run, cycle, model, a.grip, focus, drive, s.start)
        queue = ordered(todo, held_value(camset.read(ref), todo[0]["own_key"]), every)
        retried, in_a_row = set(), 0
        while queue:
            t = queue.pop(0)
            if routes.get(t["label"]) is None:
                continue
            try:
                lines.append(register(cam, link, hdmi, run, cycle, model, labels, axes, t, routes[t["label"]],
                                      a.grip, setup, out, hold_allowed(a.allow)))
                in_a_row = 0
            except PutOff:
                if t["label"] not in retried:
                    retried.add(t["label"])
                    queue.append(t)
                    print(f"  {t['label']}: the registration holds it before the hold; tried again at the end",
                          flush=True)
                else:
                    print(f"  {t['label']}: the registration still holds it: left for another run", flush=True)
            except Failed as e:
                print(f"  {t['label']}: {e}", flush=True)
                close_screen(cam, link)
                in_a_row += 1
                if in_a_row == 3:
                    print("three areas in a row failed: stopping", flush=True)
                    break
    done = {ln["label"] for ln in lines if ln["applied"]}
    missed = [t["label"] for t in todo if t["label"] not in done]     # a setup that stopped the run leaves them all
    print(f"registered and proved: {len(todo) - len(missed)} of {len(todo)}"
          + (f"; not proved: {missed}" if missed else ""), flush=True)
    return 0 if not missed else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--areas", default="missing",
                    help="missing (default), all, or the definition's labels, comma-separated ('Spot: S,Tracking: Custom 2')")
    ap.add_argument("--grip", choices=("down", "up"), default=None,
                    help="the owner holds the camera vertically: Switch V/H AF Area = AF Point + AF Area, that "
                         "orientation's copies, the turned dialog read upright")
    ap.add_argument("--focus-mode", choices=("auto", "menu", "leave"), default="auto",
                    help="auto: set Focus Mode = Continuous AF through the menu (its dial set with the menu) when the "
                         "plan holds a Tracking area; menu: always; leave: as the camera has it")
    ap.add_argument("--drive-mode", choices=("auto", "menu", "leave"), default="auto",
                    help="auto: set Drive Mode Dial = Set with Menu and Drive Mode = Single Shooting through the menu "
                         "when the plan holds a Tracking area (the camera refuses Continuous AF under some drive "
                         "modes); menu: always; leave: as the camera has it")
    add_scan_argument(ap, default=LATEST_SCAN, mode="Stills")
    ap.add_argument("--run", default="kit2_afreg2")
    ap.add_argument("--context", default=None, help="more of the state these proofs are made in")
    ap.add_argument("--limit", type=int, default=0, help="the first N areas of the plan only")
    ap.add_argument("--list", action="store_true", help="print the plan only; no camera")
    ap.add_argument("--proved", action="store_true", help="print the codes the run's applied lines proved; no camera")
    add_allow_argument(ap)
    a = ap.parse_args(argv)
    if a.proved:
        got = proved_codes(jsonl.read(paths.run_root() / a.run / "proofs.jsonl"))
        for k, codes in got.items():
            print(f"{k}: {codes}")
        if not got:
            print("no applied proof in the run")
        return 0
    doc = definitions.with_evidence(read_json(definitions.active()), definitions.active())
    todo = plan(doc, a.areas, a.grip)
    if a.limit:
        todo = todo[:a.limit]
    tracking = any(t["label"].startswith("Tracking") for t in todo)
    focus = a.focus_mode == "menu" or (a.focus_mode == "auto" and tracking)
    drive = a.drive_mode == "menu" or (a.drive_mode == "auto" and tracking)
    context = context_of(a.grip, a.context)
    sets = [step_name(k, w) for k, w in setup_steps(a.grip, focus, drive)]
    print(f"{len(todo)} areas to register ({ORIENTATIONS[a.grip]}; context {context!r}; run {a.run}):", flush=True)
    try:
        from pass3_run import labels_of
        from prove_run import AXES
        labels, _ = labels_of([ROW])
        axes = {o: info for o, info in read_json(AXES).get(ROW, {}).items() if len(info["values"]) > 1}
    except (SystemExit, OSError, ValueError):
        labels, axes = None, None
    for t in todo:
        r = route(t["label"], labels, axes) if labels else None
        way = (f"carousel {labels[r[0]]!r}" + (f", axis {axes[r[1]]['values'][r[2]]!r}" if r[1] else "")) if r \
            else "no route in pass 1's map and the axis walk"
        print(f"  {t['label']} (code {t['code']}): {way}; expects "
              + ", ".join(f"{k}={v}" for k, v in t["expected"].items()), flush=True)
    print(f"set through the menu first: {'; '.join(sets)}; the start file put back at the end puts them back",
          flush=True)
    if a.list or not todo:
        return 0
    if not hold_allowed(a.allow):
        sys.exit(f"afreg_run: Fn held on the shooting screen registers an area (a registration; docs/decisions/0021): a "
                 f"run holds it only with the owner's word, --allow {FN_HOLD!r}")
    others = [x for x in a.allow if not hold_allowed([x])]
    if others:
        sys.exit(f"afreg_run: --allow names {others}: this run is allowed nothing but {FN_HOLD!r}")
    return prove(a, doc, todo, focus, drive, context, allowed_or_exit(a.allow))


if __name__ == "__main__":
    sys.exit(main())
