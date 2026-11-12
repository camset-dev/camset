"""Spot-check that registering a memory slot copies each live record into the set record of the same id (2026-11-09).

    .venv/bin/python kit/tools/set_twins.py --evidenced RUN|''       the groups and the rows to change (no camera)
    .venv/bin/python -u kit/provers/memreg_run.py --list             the plan (no camera)
    .venv/bin/python -u kit/provers/memreg_run.py --allow "Camera Set. Memory" [--limit N] [--rows "Aspect Ratio" ...]

The hypothesis: a memory set record with the same id as a live record is that setting's copy; registering the slot
copies live to set, recalling it copies set to live. Today's two registrations of slot 1 (runs/<model>_fw<fw>/
kit2_small_1109, drive.jsonl) showed 43 set records take the live values (set1:0x0290 and 0x0292 after Shading Comp.
and Chromatic Aberration Comp. were set Off), and every set 1 twin equal to its live record after each. This run
changes a few dozen more live settings, each through its own menu row, and registers the slot again.

The rows are the ones kit/tools/set_twins.py picked (runs/<camera>/kit2_memtwins/set_twins.json: plain list rows, one
setting each, spread over the tabs, nothing that makes sound, light or motion, changes the mode, touches the cards or
what the screen shows), or those --rows names among its candidates. Each row's option is chosen again from this run's
start file: the first of the row's options, in the menu's order, that the live record does not hold. The console and
the run folder (spotcheck.json, proofs.jsonl) name the option each row chose, which on a row of few options can tell
what its record held; both are local (runs/ is never versioned), and no other value a record held is printed
(docs/decisions/0016).

One session, bracketed as every run is (decision 15; runner.prover_session):
  a. Baseline registration: MENU, the MR Camera Set. Memory row by the page scan (--scan), its lit text read, Enter.
     The row is never-open (an action): a camera run opens it only when given --allow "Camera Set. Memory", the owner's
     word (they allowed it remotely on 2026-11-09: drive.py --allow, kit2_small_1109), and each proof line says so
     ("allowance", runner.allowed_or_exit). The slot screen ("MR Memory", tabs 1 2 3 M1 M2 M3 M4, the lit tab
     a small orange square: kit2_small_1109 00013, 00021, 00154 and 00282_enter.png) must read Memory and no Movie, S&Q
     or Time-lapse; the lit tab must be the slot's (lit_tab: where the orange square sits in the tab row; tab 1 at
     x 224-273 on all four frames, the other tabs placed 60 px apart by the frame's own labels, never seen lit), so
     Enter never falls on M1-M4, which register to the card; a lit tab that cannot be measured, after one fresh look,
     fails the registration before Enter (never assumed); then Enter as drive.py's vouched "enter!:Memory" sends
     it (press_decision: the kit's reader cannot size the square, so the lit text is unread; the screen's whole text
     must name nothing never-open but the row allowed). The camera says "Registered." (00155_enter.png, no
     confirmation, a filled slot overwritten at once) and goes back to the menu by itself (00156). MENU out,
     download A: the slot now holds the live values.
  b. Each row set through the menu (kit/provers/mode_switch.py set_row: the row by the scan, Right, Down to the
     option, OK), MENU out between rows. A row the camera refuses ("not available as follows" after OK) has its
     notice closed with its OK and is kept as refused, its notice's text in spotcheck.json only; a row that fails
     (not reached, its option not found) is skipped; three in a row end the changes. Download B.
  c. Register the slot again (as a.), download C.
  d. Judge, per row: the live record changed from A to B (else "the setting did not take"), and the slot's copy in C
     holds the live record's bytes of B (else "no mirror"); notes when the baseline left the copy unlike the live
     record, when the copy moved before the second registration, or when the live record moved during it. Also every
     other record of the slot that changed from A to C (the chosen changes' side effects, each with its group from
     set_twins and whether it now equals its live twin) and every other live record that changed from A to B (with
     whether its copy took it), and the live records the registration itself changed (B to C). Written to the run's
     spotcheck.json, and one proof line per row whose setting took into its proofs.jsonl: {"path": ["Camera Set.
     Memory", <setting>], "kind": "registration mirror", "record": "set:<id>", "live": "global:<id>", "index": <the
     option's code>, "label": <the option>, "base": A, "changed": B, "dat"/"after": C, "changes": the copy's change
     from A to C, "applied": mirrored, ...}. The run folder is marked as one of the camera's proof runs
     (camkit.runs.PROOF_RUN): kit/pass2_report.py keeps the lines out of its rows and its registration_mirrors hands
     each mirrored live record to kit/schema_update.py, which marks that setting's memory copy proved
     ("in_sets_proved": the run, the day, the slot) and adds the line's allowance to its note's evidence.
  e. The start file goes back on and the restore is checked (exit EXIT_UNRESTORED when it did not take). Three records
     of the slot no settings file sets (NOT_BY_FILE): the slot's filled mark, its registration family and the exposure
     mode it was registered in (set1:0x023c, 0x11ab, 0x11ad on the a1 II: kit2_small_1109 00159_restored.DAT and
     00289_restored.DAT, the only records left differing after an upload). The restore check says them by key and
     leaves them out (runner.prover_session's expected). The start file must already have the slot filled (the run
     checks it before any press; today's start has it): registering an empty slot would fill it for good, so this run
     never does.

Options: --allow (the owner's word for Camera Set. Memory; a camera run refuses to start without it), --rows
(repeatable, a candidate's path with " > "; default: set_twins' picks), --limit, --list (no camera),
--scan (the Stills page scan; default: the camera's latest Stills page scan, runner.latest_scan), --slot (1 only: the frames show tab 1 lit), --survey (the
set_twins.json to read), --run (default kit2_memtwins, beside the survey).
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parent))
sys.path.insert(2, str(Path(__file__).resolve().parents[1] / "tools"))
from camkit import camset, definitions, match, paths, safety  # noqa: E402
from runner import (LATEST_SCAN, add_allow_argument, add_scan_argument, allowed_or_exit, read_json,  # noqa: E402
                    scan_dir, write_json)
import set_twins  # noqa: E402

MEMORY_ROW = "Camera Set. Memory"
KIND = "registration mirror"
RUN = set_twins.RUN
SLOTS = ("1",)                       # only tab 1 has been seen lit (lit_tab)
# the slot screen's tab row: the orange square of the lit tab (kit2_small_1109 00013, 00021, 00154, 00282_enter.png:
# x 224-273, y within the top 56 rows), the labels 60 px apart (1 2 3 M1 M2 M3 M4)
TABS = ("1", "2", "3", "M1", "M2", "M3", "M4")
TAB_X, TAB_STEP, TAB_STRIP, TAB_WIDTH, TAB_HEIGHT, TAB_SLACK = 248, 60, 80, (40, 60), (28, 60), 15
SLOT_SCREEN = re.compile(r"\bmemory\b", re.I)
NOT_STILLS = re.compile(r"movie|s\s*&\s*q|time-?\s?lapse", re.I)
# The records of a slot no settings file sets (an upload leaves them as the last registration wrote them), by model:
# its filled mark, its registration family, the exposure mode it was registered in (kit2_small_1109: 00159_restored.DAT
# and 00289_restored.DAT differ from the files before the registrations in these alone). And the filled mark's code
FILLED_MARK = {"ILCE-1M2": (0x023c, 4)}
NOT_BY_FILE = {"ILCE-1M2": (0x023c, 0x11ab, 0x11ad)}


# ---------------------------------------------------------------- the plan (no camera)

def survey_rows(survey: dict, asked=None) -> list:
    """The candidates to change: set_twins' picks, in its order, or the ones `asked` names (paths with " > ") among
    the candidates it found eligible; exits naming a row it does not know or left out."""
    cands = {" > ".join(c["path"]): c for c in survey.get("candidates") or []}
    if not asked:
        return [cands[" > ".join(p)] for p in survey.get("picked") or []]
    out = []
    for name in asked:
        c = cands.get(name)
        if c is None:
            sys.exit(f"memreg_run: --rows {name!r} is not among set_twins' candidates (a twin's plain list row)")
        if c.get("excluded"):
            sys.exit(f"memreg_run: --rows {name!r} was left out by set_twins: {c['excluded']}")
        out.append(c)
    return out


def section_of(slot: str) -> int:
    """The file section of a Stills slot (the camera section's memory_sets: section 1 is Memory 1)."""
    return int(slot)


def expected_keys(model: str, section: int) -> frozenset:
    """The keys of the slot's records no settings file sets, which a registration writes (NOT_BY_FILE)."""
    return frozenset(f"set{section}:{set_twins.hexid(r)}" for r in NOT_BY_FILE.get(model, ()))


def slot_filled(cs, model: str, section: int) -> bool:
    rid, code = FILLED_MARK[model]
    rec = cs.get(section, rid)
    return rec is not None and rec.value() == code


def tab_box(image) -> tuple | None:
    """(x0, x1) of the slot screen's lit tab square: the orange mask closed as camkit.live closes it (a square whose
    fill is patchy still merges), the regions in the tab strip (the top TAB_STRIP rows, the whole width), the one
    TAB_WIDTH wide and TAB_HEIGHT high with the most orange; None when there is none."""
    import cv2
    import numpy as np

    from camkit import screen
    from camkit.live import CLOSE
    lit = (screen._orange(image) > 0.5)[:TAB_STRIP, :]
    closed = cv2.morphologyEx(lit.astype(np.uint8), cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, CLOSE))
    n, _, stats, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    best = None
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i, :5])
        if TAB_WIDTH[0] <= w <= TAB_WIDTH[1] and TAB_HEIGHT[0] <= h <= TAB_HEIGHT[1] and (best is None or area > best[0]):
            best = (area, x, x + w - 1)
    return None if best is None else (best[1], best[2])


def lit_tab(image) -> str | None:
    """The slot screen's lit tab, by where its orange square sits in the tab strip (tab_box): its middle within
    TAB_SLACK of a tab's place; None when there is none, or it is not one tab's."""
    box = tab_box(image)
    if box is None:
        return None
    mid = (box[0] + box[1]) / 2
    i = round((mid - TAB_X) / TAB_STEP)
    if not 0 <= i < len(TABS) or abs(mid - (TAB_X + i * TAB_STEP)) > TAB_SLACK:
        return None
    return TABS[i]


# ---------------------------------------------------------------- the judgement (no camera)

def judge(rows: list, a, b, c, section: int, group_of: dict) -> dict:
    """The verdict from the three downloads (Camsets): A after the baseline registration, B after the rows were set, C
    after the second registration. rows: the step-b results ({"record", "key", "setting", "path", "option", "code",
    "status"}). group_of: {record id: "flagged" | "unflagged" | "set_defined" | "set_only"}. Keys and true/false only:
    no value is kept here (the downloads hold them)."""
    out, chosen = [], set()
    for r in rows:
        rid = int(r["record"], 16)
        chosen.add(rid)
        la, lb, lc = (x.get(0, rid) for x in (a, b, c))
        sa, sb, sc = (x.get(section, rid) for x in (a, b, c))
        live_changed = la.raw != lb.raw
        mirrored = live_changed and sc.raw == lb.raw
        notes = []
        if sa.raw != la.raw:
            notes.append("after the baseline registration the copy is unlike the live record")
        if sb.raw != sa.raw:
            notes.append("the copy moved before the second registration")
        if lc.raw != lb.raw:
            notes.append("the live record moved during the second registration")
        if live_changed and r.get("status") != "set":
            notes.append(f"the live record moved although the row was {r.get('status')}")
        verdict = "mirrored" if mirrored else ("no mirror" if live_changed else "the setting did not take")
        out.append({"record": f"set:{set_twins.hexid(rid)}", "live": r["key"], "setting": r["setting"],
                    "path": r["path"], "option": r.get("option"), "code": r.get("code"), "status": r.get("status"),
                    "live_changed": live_changed, "mirrored": mirrored, "verdict": verdict, "notes": notes,
                    **{k: r[k] for k in ("why", "notices") if r.get(k)}})

    def twin_equal(cs, rid):
        live, copy = cs.get(0, rid), cs.get(section, rid)
        return None if live is None or copy is None else live.raw == copy.raw
    others = [{"key": ch.key, "group": group_of.get(ch.id, "?"), "equals_live_after": twin_equal(c, ch.id)}
              for ch in camset.diff(a, c, sections={section}) if ch.id not in chosen]
    live_side = []
    for ch in camset.diff(a, b, sections={0}):
        if ch.id in chosen:
            continue
        copy = c.get(section, ch.id)
        live_side.append({"key": ch.key, "twin": copy is not None,
                          "mirrored": None if copy is None else copy.raw == b.get(0, ch.id).raw})
    by_registration = [ch.key for ch in camset.diff(b, c, sections={0})]
    elsewhere = [ch.key for ch in camset.diff(a, c) if ch.section not in (0, section)]
    took = [x for x in out if x["live_changed"]]
    counts = {"rows": len(out), "set": sum(x["status"] == "set" for x in out), "took": len(took),
              "mirrored": sum(x["mirrored"] for x in out), "no_mirror": sum(not x["mirrored"] for x in took),
              "did_not_take": len(out) - len(took), "other_slot_records": len(others),
              "other_slot_unflagged": sum(o["group"] == "unflagged" for o in others),
              "live_side_effects": len(live_side), "other_sets_changed": len(elsewhere)}
    return {"rows": out, "other_slot_records": others, "live_side_effects": live_side,
            "live_changed_by_registration": by_registration, "other_sets_changed": elsewhere, "counts": counts}


def proof_lines(verdict: dict, section: int, slot: str, downloads: dict, frames: dict, a, c) -> list:
    """One proof line per row whose setting took (the kit's proof shape; kind "registration mirror"): the copy's change
    from A to C, applied when it mirrored the live record."""
    lines = []
    for x in verdict["rows"]:
        if not x["live_changed"]:
            continue
        rid = int(x["record"].split("0x")[1], 16)
        key = f"set{section}:{set_twins.hexid(rid)}"
        ch = [{"key": key, "before": a.get(section, rid).value(), "after": c.get(section, rid).value()}] \
            if a.get(section, rid).raw != c.get(section, rid).raw else []
        why = None if x["mirrored"] else "the copy does not hold the live record's new bytes after the registration"
        lines.append({"path": [MEMORY_ROW, x["setting"]], "menu": MEMORY_ROW, "kind": KIND, "record": x["record"],
                      "live": x["live"], "key": key, "row": x["path"], "index": x.get("code"), "label": x["option"],
                      "via": f"{' > '.join(x['path'])} = {x['option']} chosen in the menu, then slot {slot} registered "
                             f"({MEMORY_ROW}, Enter on the slot)",
                      "slot": slot, "base": downloads["A"], "changed": downloads["B"], "dat": downloads["C"],
                      "after": downloads["C"], "changes": ch, "applied": x["mirrored"],
                      **({"not_applied": why} if why else {}), "notes": x["notes"] + [n for f in frames.values() for n in f.get("notes", [])],
                      "frames": frames})
    return lines


def scrub(msg: str) -> str:
    """A failure as printed: without the list's lit option (set_row's "(on '...')"), which can be the held one."""
    return re.sub(r"\s*\(on '.*?'\)", "", msg)


# ---------------------------------------------------------------- the camera

class RefusedRow(Exception):
    """The camera refused the option ("not available as follows ..." after OK): the notice's text."""


def watcher(cam, notes: list, say):
    """set_row's `say`: its choice said as it is; a notice after OK kept in `notes`, not printed (it can name another
    setting's value), and when it reads "not available", closed with its OK (MENU is refused on it) and the row
    refused; an information screen after the choice kept too."""
    from mode_switch import text

    def watch(msg: str):
        if "notice after OK" in msg:
            t = " ".join(text(cam).split())
            notes.append(t)
            if re.search(r"not\s+available", t, re.I) and not safety.confirmation(t):
                cam.press("enter")
                raise RefusedRow(t)
            say("   a notice after OK, closed with MENU (its text is in spotcheck.json)")
            return
        if "information after the choice" in msg:
            # set_row says the frame only; the screen's words are in events.jsonl (set_row_information)
            m = re.search(r"\(([^;()]+);", msg)
            notes.append(f"an information screen after the choice ({m.group(1) if m else 'frame not said'}), taken "
                         "with its OK: its words are in events.jsonl under set_row_information")
            say("   an information screen after the choice, taken with its OK")
            return
        say(msg)
    return watch


def memory_allowed(allow) -> bool:
    """--allow names the Camera Set. Memory row (compared as the guards fold labels)."""
    want = safety.clean_label(safety.fold(MEMORY_ROW))
    return any(safety.clean_label(safety.fold(x)) == want for x in allow or ())


def register_slot(cam, cycle, model, slot: str, say, allow=(MEMORY_ROW,)) -> dict:
    """Step a. (and c.): the slot registered, back on the menu. Fails before Enter when the row, the screen or the lit
    tab is not the one expected."""
    from camkit.live import lit_text, text_of
    from drive import highlighted, press_decision
    from mode_switch import find, open_menu
    from prove_run import Failed
    open_menu(cam)
    find(cam, cycle, model, MEMORY_ROW)
    lit = lit_text(cam.frame.image, cam.frame.path)
    if match.key(MEMORY_ROW) not in match.key(lit):
        raise Failed(f"the lit row reads {lit!r}, not {MEMORY_ROW} ({cam.frame.path.name})")
    row_frame = cam.frame.path.name
    cam.press("enter")                  # LiveCamera's row check: never-open, and this run's may_open names it
    t, kind = text_of(cam), cam.read().kind
    if not SLOT_SCREEN.search(t) or NOT_STILLS.search(t):
        raise Failed(f"Enter on {MEMORY_ROW} opened {kind}, not the Stills memory slots ({cam.frame.path.name})")
    tab = lit_tab(cam.frame.image)
    if tab is None:                     # re-read the screen once, on a fresh frame
        first = cam.frame.path.name
        cam.refresh("slot-tab")
        t = text_of(cam)
        tab = lit_tab(cam.frame.image)
        if tab is None:                 # never assumed: Enter on M1-M4 registers to the card, which no file puts back
            raise Failed(f"the slot screen's lit tab could not be measured ({first}, then {cam.frame.path.name}): no "
                         "Enter on a tab the kit cannot place")
    if tab != slot:
        raise Failed(f"the slot screen lights {f'tab {tab}' if tab else 'no tab the kit can place'}, not {slot} "
                     f"({cam.frame.path.name})")
    why, vouched = press_decision("enter!:Memory", "enter", highlighted(cam.frame.image, cam.frame.path), t, kind,
                                  False, tuple(allow))
    if why:
        raise Failed(f"Enter on slot {slot} refused: {why} ({cam.frame.path.name})")
    slot_frame = cam.frame.path.name
    cam.press("enter")
    said = ""
    for _ in range(3):                  # the notice shows about a second (00155), then the menu is back (00156)
        said = text_of(cam)
        if re.search(r"\bregistered\b", said, re.I) or cam.read().kind in ("menu", "submenu"):
            break
        time.sleep(0.3)
        cam.refresh("registered")
    ok = bool(re.search(r"\bregistered\b", said, re.I))
    say(f"slot {slot}: {'Registered.' if ok else 'no Registered. read (the downloads will tell)'} "
        f"({'vouched ' if vouched else ''}Enter on {slot_frame}, then {cam.frame.path.name})")
    return {"row_frame": row_frame, "slot_frame": slot_frame, "said_frame": cam.frame.path.name, "said": ok,
            "vouched": vouched}


def download(cam, link, hdmi, tag: str):
    """Back to the shooting screen, a download, and the menu lock's wait after it."""
    from prove_run import LOCK_S, to_shooting
    from runner import close_screen
    close_screen(cam, link)
    to_shooting(link, hdmi, f"the download {tag}")
    time.sleep(1)
    got = link.download(tag)
    time.sleep(LOCK_S)
    return got


def set_rows(cam, link, cycle, model, todo: list, start_cs, say, partial=None) -> list:
    """Step b.: each row on its option (chosen from the start file), MENU out after each. Three failures in a row end
    the changes. Returns the rows' results."""
    from mode_switch import open_menu, set_row
    from prove_run import Failed
    from runner import close_screen
    out, in_a_row = [], 0
    if partial is not None:
        partial["rows"] = out            # the caller keeps the list as it grows
    for c in todo:
        label, code = set_twins.option_for(c, start_cs)
        r = {"record": c["record"], "key": c["key"], "setting": c["setting"], "path": c["path"], "option": label,
             "code": code}
        notes = []
        if label is None:
            r.update(status="skipped", why="no option the live record does not hold")
            out.append(r)
            continue
        try:
            open_menu(cam)
            set_row(cam, cycle, model, c["path"], label, watcher(cam, notes, say))
            r["status"] = "set"
            in_a_row = 0
        except RefusedRow:
            r["status"] = "refused"
            say("   refused by the camera (the notice's text is in spotcheck.json)")
        except Failed as e:
            r.update(status="skipped", why=scrub(str(e)))
            say(f"   skipped: {r['why']}")
            in_a_row += 1
        if notes:
            r["notices"] = notes
        close_screen(cam, link)
        time.sleep(1.0)
        out.append(r)
        if in_a_row == 3:
            say("three rows in a row failed: no more rows")
            break
    return out


def prove(a, doc: dict, todo: list, survey: dict, allowance: str) -> int:
    from camkit.frames import eyes_from_config
    from camkit.runs import Run
    from prove_run import Failed
    from runner import load_scan, proofs_file, prover_session
    model_name = doc.get("model") or definitions.key(doc).split("_fw")[0]
    section = section_of(a.slot)
    expected = expected_keys(model_name, section)
    cycle, model = load_scan(a.scan)
    scan_name = scan_dir(a.scan).name           # the folder load_scan read, for the proof lines
    run = Run(a.run)
    hdmi = eyes_from_config(run)
    say = lambda m: print(m, flush=True)     # noqa: E731
    group_of = {int(x["record"], 16): g for g in ("flagged", "unflagged", "set_defined", "set_only")
                for x in survey.get(g) or []}
    result = {}
    partial = {"rows": []}
    with proofs_file(run, None, {"allowance": allowance} if allowance else None) as out, \
            prover_session(run, hdmi, may_open=set(a.allow), show=0, expected=expected,
                           end_why="the settings download after the registrations") as s:
        cam, link = s.cam, s.link
        start_cs = camset.read(s.start)
        if not slot_filled(start_cs, model_name, section):
            raise Failed(f"slot {a.slot} is empty in the start file: registering it would fill it for good (no settings "
                         "file empties it); this run registers a filled slot only")
        say(f"slot {a.slot} is filled in the start file; {len(todo)} rows to change")
        frames, dl, rows = {}, {}, []
        try:
            frames["a"] = register_slot(cam, cycle, model, a.slot, say, a.allow)
            dl["A"] = download(cam, link, hdmi, "registered-a")
            rows = set_rows(cam, link, cycle, model, todo, start_cs, say, partial=partial)
            dl["B"] = download(cam, link, hdmi, "changed-b")
            frames["c"] = register_slot(cam, cycle, model, a.slot, say, a.allow)
            dl["C"] = download(cam, link, hdmi, "registered-c")
        except BaseException as e:           # a stopped run keeps what it has (the rows set, the skips, the failure)
            write_json(run.dir / "spotcheck.json",
                       {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "slot": a.slot, "section": section,
                        "scan": scan_name, "start": s.start.name, "stopped": scrub(f"{type(e).__name__}: {e}"),
                        "downloads": {k: p.name for k, p in dl.items()}, "registrations": frames,
                        "rows": partial["rows"] or rows}, indent=1)
            say(f"the run stopped before its judgement: spotcheck.json holds the {len(partial['rows'] or rows)} rows "
                "so far")
            raise
        cs = {k: camset.read(p) for k, p in dl.items()}
        verdict = judge(rows, cs["A"], cs["B"], cs["C"], section, group_of)
        names = {k: p.name for k, p in dl.items()}
        lines = proof_lines(verdict, section, a.slot, names, frames, cs["A"], cs["C"])
        for line in lines:
            out.write(json.dumps(line) + "\n")
        out.flush()
        if lines:
            from camkit.runs import mark_proof_run
            mark_proof_run(run.dir, "kit/provers/memreg_run.py")     # the report and the writer read its mirrors
        result = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "slot": a.slot, "section": section, "scan": scan_name,
                  "start": s.start.name, "downloads": names, "registrations": frames,
                  "restore_leaves_out": sorted(expected), **verdict}
        write_json(run.dir / "spotcheck.json", result, indent=1)
        say_verdict(verdict, section, say)
    if not result:
        print("the run stopped before its judgement: nothing judged", flush=True)
        return 1
    n = result["counts"]
    return 0 if n["took"] and n["no_mirror"] == 0 else 1


def say_verdict(v: dict, section: int, say):
    """Counts and names: each row's option chosen and its verdict, never a value."""
    for x in v["rows"]:
        extra = f"; {'; '.join(x['notes'])}" if x["notes"] else ""
        say(f"  {' > '.join(x['path'])} = {x['option']!r}: {x['verdict']} ({x['status']}){extra}")
    n = v["counts"]
    say(f"rows: {n['rows']}, set {n['set']}, took {n['took']}, mirrored {n['mirrored']}, no mirror {n['no_mirror']}, "
        f"did not take {n['did_not_take']}")
    if v["other_slot_records"]:
        say(f"other set{section} records changed from A to C: {n['other_slot_records']} "
            f"({n['other_slot_unflagged']} unflagged twins): "
            + ", ".join(f"{o['key']} [{o['group']}{', = live' if o['equals_live_after'] else ''}]"
                        for o in v["other_slot_records"]))
    if v["live_side_effects"]:
        say(f"other live records changed from A to B: {n['live_side_effects']}: "
            + ", ".join(f"{o['key']}{' (copy took it)' if o['mirrored'] else ''}" for o in v["live_side_effects"]))
    if v["live_changed_by_registration"]:
        say(f"live records the registration changed: {', '.join(v['live_changed_by_registration'])}")
    if v["other_sets_changed"]:
        say(f"WARNING: records of other memory sets changed: {', '.join(v['other_sets_changed'])}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    add_allow_argument(ap)
    ap.add_argument("--rows", action="append", default=None,
                    help="a row to change, its path with ' > ' (default: kit/tools/set_twins.py's picks)")
    ap.add_argument("--limit", type=int, default=0, help="the first N rows only")
    ap.add_argument("--list", action="store_true", help="print the plan only; no camera")
    add_scan_argument(ap, default=LATEST_SCAN, mode="Stills")
    ap.add_argument("--slot", choices=SLOTS, default="1", help="the Stills memory slot to register (1)")
    ap.add_argument("--survey", default=None, help="set_twins.json (default: runs/<camera>/kit2_memtwins/)")
    ap.add_argument("--run", default=RUN)
    a = ap.parse_args(argv)
    root = paths.run_root()
    doc = definitions.with_evidence(read_json(definitions.active()), definitions.active())
    camera = definitions.key(doc)
    model_name = doc.get("model") or camera.split("_fw")[0]
    if model_name not in NOT_BY_FILE:
        sys.exit(f"memreg_run: which of a {model_name} slot's records no settings file sets is not known (NOT_BY_FILE): "
                 "find them first (register by hand with drive.py, restore, and compare)")
    survey_file = Path(a.survey) if a.survey else set_twins.out_path(root)
    if not survey_file.exists():
        sys.exit(f"memreg_run: no {survey_file}: run kit/tools/set_twins.py --evidenced <run> first "
                 "(the run that registered the slot already, or --evidenced '' for none)")
    survey = read_json(survey_file)
    if survey.get("camera") != camera:
        sys.exit(f"memreg_run: {survey_file} is {survey.get('camera')}'s, not {camera}'s")
    todo = survey_rows(survey, a.rows)
    if a.limit:
        todo = todo[:a.limit]
    section = section_of(a.slot)
    n = survey["counts"]
    print(f"{camera}: {n['twins']} twins: {n['flagged']} flagged in_sets, {n['unflagged']} unflagged (no live setting "
          f"names them: {n['candidates_unflagged']} plain list rows among them), {n['set_only']} set records with no "
          f"live record, {n['set_defined']} set: settings (set_twins, {survey.get('file')})")
    print(f"{len(todo)} rows to change, then slot {a.slot} registered (set{section}); the option of each is chosen again "
          f"from the run's start file (shown: from the survey's file):")
    for i, c in enumerate(todo, 1):
        print(f"  {i:2d}. {' > '.join(c['path'])} [{c['tab']} / {c['group']}, {c['twin']} twin of "
              f"set{section}:{c['record']}]: set {c.get('option')!r}")
    expected = expected_keys(model_name, section)
    print(f"steps: a. register slot {a.slot} ({MEMORY_ROW}, Enter on the slot, operator-vouched), download A; "
          f"b. set the rows (mode_switch.set_row), download B; c. register slot {a.slot}, download C; d. judge; "
          f"e. restore the start file")
    print(f"the restore check leaves out {', '.join(sorted(expected))}: a registration writes them and no settings file "
          f"sets them; the start file must have slot {a.slot} filled already")
    print(f"results: {paths.shown(root / a.run / 'spotcheck.json')} and {paths.shown(root / a.run / 'proofs.jsonl')}")
    if a.list or not todo:
        return 0
    if not memory_allowed(a.allow):
        sys.exit(f"memreg_run: {MEMORY_ROW} is never-open (an action); a run opens it only with the owner's word, "
                 f"--allow {MEMORY_ROW!r}")
    others = [x for x in a.allow if not memory_allowed([x])]
    if others:
        sys.exit(f"memreg_run: --allow names {others}: this run opens no never-open row but {MEMORY_ROW}")
    return prove(a, doc, todo, survey, allowed_or_exit(a.allow))


if __name__ == "__main__":
    sys.exit(main())
