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
     must name nothing never-open but the row allowed). The slot screen reads as no known kind, on which no Enter goes
     by its shape (safety.enter_refused, 2026-11-14): the run's --allow is the consent to answer it (press_decision's
     consent, the camera's answer_once), the confirmation words still judged. The camera says "Registered." (00155_enter.png, no
     confirmation, a filled slot overwritten at once) and goes back to the menu by itself (00156). MENU out,
     download A: the slot now holds the live values.
  b. Each row set through the menu (kit/provers/mode_switch.py set_row: the row by the scan, Right, Down to the
     option, OK), MENU out between rows. A row the camera refuses ("not available as follows" after OK) has its
     notice left with MENU, and with its OK where the camera refuses MENU and OK is its only button
     (camkit.live.leave_notice), and is kept as refused, its notice's text in spotcheck.json only; a row that fails
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
from camkit.not_by_file import NOT_BY_FILE  # noqa: E402
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
# The records of a slot no settings file sets are camkit.not_by_file's NOT_BY_FILE, by model; the first, its filled
# mark, and the mark's code
FILLED_MARK = {"ILCE-1M2": (0x023c, 4)}


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


# ---------------------------------------------------------------- --aperture: each F-number registered into the slot

APERTURE_SET = 0x0180               # a memory set's exposure record: the F-number (F x 100) at byte APERTURE_AT
APERTURE_COPIES = 0x018c            # the live record that keeps every set's exposure too, a set's block SET_BLOCK long
APERTURE_AT, SET_BLOCK = 288, 320


def aperture_keys(section: int) -> tuple:
    """The definition's keys of the F-number a registration of the slot of `section` writes: its set record's field,
    and that set's block in the live copies' record (section 1 at byte 288, each next set 320 bytes on)."""
    return (f"set:{set_twins.hexid(APERTURE_SET)}@{APERTURE_AT}",
            f"global:{set_twins.hexid(APERTURE_COPIES)}@{APERTURE_AT + SET_BLOCK * (section - 1)}")


def slot_apertures(cs, section: int) -> dict:
    """{key: the F-number (F x 100) it holds, or None where it cannot be read} for aperture_keys(section) in `cs`."""
    out = {}
    for key, (sec, rid) in zip(aperture_keys(section), ((section, APERTURE_SET), (0, APERTURE_COPIES)), strict=True):
        at = int(key.rsplit("@", 1)[1])
        rec = cs.get(sec, rid)
        raw = rec.raw[at:at + 2] if rec is not None else b""
        out[key] = int.from_bytes(raw, "little") if len(raw) == 2 else None
    return out


FILL_EMPTY_WORD = ("the owner's word of 2026-11-20 for the aperture run: \"go ahead with the run, obviously the lens "
                   "could limit the aperture\", told that a registration fills an empty slot for good")


def slot_refused(cs, model: str, section: int, slot: str, fill_empty: bool) -> str:
    """Why the slot of `section` may not be registered from the start file `cs`, or "": an empty slot is refused (a
    registration fills it for good: the filled mark is one of the records no settings file sets), unless `fill_empty`
    (--fill-empty-slot, FILL_EMPTY_WORD): the slot then stays registered after the run, its values the start file's."""
    if slot_filled(cs, model, section) or fill_empty:
        return ""
    return (f"slot {slot} is empty in the start file: registering it would fill it for good (no settings file empties "
            "it); this run registers a filled slot only, unless --fill-empty-slot gives the owner's word")


def not_offered(lens: list, asked) -> list:
    """The F-numbers --values names that the lens does not offer (the camera's list): said, never set."""
    return sorted(v for v in (asked or ()) if v not in set(lens))


def aperture_order(values: list, held, only=None) -> list:
    """The F-numbers to register, each once: the lens's list as the camera gives it (`values`, F x 100), or those of
    `only` among it, the one the camera holds (`held`) last, so the live aperture ends where it began."""
    vals = [v for v in dict.fromkeys(values) if only is None or v in only]
    return [v for v in vals if v != held] + ([held] if held in vals else [])


def f_label(v: int) -> str:
    return f"F{v / 100:g}"


BEYOND_WORD = ("the owner's word of 2026-11-20: \"if you can get the camera to do f-numbers out the range go for it, you "
               "may need to infer as I may not have lens that cover the whole range\"")


def beyond_lens(table: list, lens: list) -> list:
    """The definition table's F-numbers (F x 100) the lens does not offer, its "—" (0) aside: --beyond-lens tries each
    once (BEYOND_WORD)."""
    return sorted(v for v in dict.fromkeys(table) if v and v not in set(lens))


def register_apertures(link, values: list, slot: str, section: int, register, download, stopped, say,
                       word: str = "not offered") -> tuple:
    """Each F-number of `values` set through the SDK (link.set("FNumber"): an exposure property camkit.safety.
    SET_PROPERTIES allows), read back, then the slot registered (`register()`) and a download made (`download(tag)`):
    the slot's two records (aperture_keys) must hold it. Between registrations only, `stopped()` (the run's STOP file)
    ends the loop: no registration is ever left half-way by it. A set the camera refuses, or reads back otherwise,
    registers nothing and is said. Returns (the proof lines, one per record a registration wrote, applied where the
    record holds the value; the values not set; whether a stop ended it)."""
    lines, not_set, before = [], [], None
    for v in values:
        if stopped():
            say(f"stopped before F-number {f_label(v)}: the registrations so far are kept, the restore puts the slot back")
            return lines, not_set, True
        try:
            link.set("FNumber", v)
            back = (link.get("FNumber") or {}).get("current")
        except Exception as e:              # the camera refused the set: never forced by another route
            not_set.append({"value": v, "why": f"{word}: {type(e).__name__}: {e}"})
            say(f"   {f_label(v)}: {word} (the camera refused it: {e}); nothing registered, nothing forced")
            continue
        if back != v:                       # a clamp, or another value kept: what it answered is kept
            not_set.append({"value": v, "why": f"{word}: read back {back}"})
            say(f"   {f_label(v)}: {word} (the camera reads back {back}); nothing registered, nothing forced")
            continue
        frames = register()
        dat, cs = download(f"aperture-{v}")
        got = slot_apertures(cs, section)
        for key, held in got.items():
            ok = held == v
            lines.append({"path": [MEMORY_ROW, "Aperture"], "menu": MEMORY_ROW, "kind": KIND, "record": key,
                          "index": v, "label": f_label(v), "slot": slot,
                          "via": f"FNumber {v} set through the SDK and read back, then slot {slot} registered "
                                 f"({MEMORY_ROW}, Enter on the slot)",
                          "base": before, "dat": dat, "after": dat, "applied": ok,
                          **({} if ok else {"not_applied": f"the record holds {held}, not {v}"}), "frames": frames})
        say(f"   {f_label(v)}: registered; " + ", ".join(f"{k} {'holds it' if got[k] == v else f'holds {got[k]}'}"
                                                         for k in got))
        before = dat
    return lines, not_set, False


def put_back_aperture(link, held, say) -> bool:
    """The live aperture the run began with set back and read back (live state no settings file holds: decision 15)."""
    try:
        link.set("FNumber", held)
        back = (link.get("FNumber") or {}).get("current")
    except Exception as e:
        say(f"the live aperture was not put back to {f_label(held)} ({e}): set it by hand (kit/tools/sdk_set.py "
            f"FNumber={held})")
        return False
    if back != held:
        say(f"the live aperture reads {back} after it was put back to {held}: set it by hand (kit/tools/sdk_set.py "
            f"FNumber={held})")
        return False
    say(f"the live aperture is back on {f_label(held)} (read back)")
    return True


def prove_apertures(a, doc: dict, allowance: str) -> int:
    """--aperture: one session (decision 15). The start download; the slot must be filled already (slot_filled: a
    registration fills an empty slot for good); the camera must take FNumber (Stills A or M); then every F-number the
    attached lens offers (the SDK's list), or --values among it, set, read back and registered (register_apertures),
    the held one last; the live aperture put back and read back; the start file uploaded and checked, which puts the
    slot's records back (the filled mark and the two records NOT_BY_FILE names aside). Proof lines in the run's
    proofs.jsonl ("registration mirror", no live record: pass2_report.mirrored_values hands them to the writer)."""
    from camkit.frames import eyes_from_config
    from camkit.runs import Run, mark_proof_run
    from prove_run import Failed
    from runner import load_scan, proofs_file, prover_session
    model_name = doc.get("model") or definitions.key(doc).split("_fw")[0]
    section = section_of(a.slot)
    cycle, model = load_scan(a.scan)
    run = Run(a.run)
    hdmi = eyes_from_config(run)
    say = lambda m: print(m, flush=True)     # noqa: E731
    only = {int(x) for x in a.values.split(",")} if a.values else None
    status = 1
    with proofs_file(run, None, {"allowance": allowance} if allowance else None) as out, \
            prover_session(run, hdmi, may_open=set(a.allow), show=0, expected=expected_keys(model_name, section),
                           end_why="the settings download after the registrations") as s:
        cam, link = s.cam, s.link
        start_cs = camset.read(s.start)
        why = slot_refused(start_cs, model_name, section, a.slot, a.fill_empty_slot)
        if why:
            raise Failed(why)
        if not slot_filled(start_cs, model_name, section):
            say(f"slot {a.slot} is empty in the start file and is filled by this run for good ({FILL_EMPTY_WORD}): it "
                "stays registered afterwards, its values the start file's")
        got = link.get("FNumber") or {}
        if not got.get("writable"):
            raise Failed("the camera does not take FNumber now (the shooting mode sets it: Stills A or M takes it)")
        held, lens = got.get("current"), list(got.get("values") or [])
        if a.beyond_lens:
            table = [v for v, _ in next((s.get("values") or [] for s in doc.get("settings") or []
                                         if s.get("key") == aperture_keys(section)[0]), [])]
            todo = beyond_lens(table, lens)
            say(f"--beyond-lens ({BEYOND_WORD}): {len(todo)} F-numbers of the table the lens does not offer, each tried "
                "once through the same SDK set; one refused or read back otherwise is recorded, never forced")
        else:
            todo = aperture_order(lens, held, only)
            missing = not_offered(lens, only)
            if missing:
                say(f"not offered by the attached lens, never set: {', '.join(f_label(v) for v in missing)}")
        if a.limit:
            todo = todo[:a.limit] + ([held] if held in todo[a.limit:] else [])
        say(f"the lens offers {len(lens)} F-numbers ({f_label(min(lens)) if lens else '-'} to "
            f"{f_label(max(lens)) if lens else '-'}); {len(todo)} to register"
            + ("" if a.beyond_lens else f", {f_label(held)} (held) last"))

        def register():
            return register_slot(cam, cycle, model, a.slot, say, a.allow)

        def dl(tag):
            p = download(cam, link, hdmi, tag)
            return p.name, camset.read(p)
        try:
            lines, not_set, stopped = register_apertures(link, todo, a.slot, section, register, dl,
                                                         lambda: (run.dir / "STOP").exists(), say,
                                                         word="refused" if a.beyond_lens else "not offered")
            if a.beyond_lens and not_set:
                write_json(run.dir / "beyond_lens.json", {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "slot": a.slot,
                                                          "lens": lens, "refused": not_set}, indent=1)
        finally:
            back = put_back_aperture(link, held, say)
        for line in lines:
            out.write(json.dumps(line) + "\n")
        out.flush()
        if lines:
            mark_proof_run(run.dir, "kit/provers/memreg_run.py")
        applied = sum(1 for x in lines if x["applied"])
        say(f"{len(lines)} proof lines, {applied} applied; {len(not_set)} F-numbers not set"
            + ("; stopped by the STOP file between registrations" if stopped else ""))
        # beyond the lens a refusal is a result, not a failure: the run is whole where every value that took applied
        status = 0 if back and applied == len(lines) and not stopped and (a.beyond_lens or (lines and not not_set)) \
            else 1
    return status


def scrub(msg: str) -> str:
    """A failure as printed: without the list's lit option (set_row's "(on '...')"), which can be the held one."""
    return re.sub(r"\s*\(on '.*?'\)", "", msg)


# ---------------------------------------------------------------- the camera

class RefusedRow(Exception):
    """The camera refused the option ("not available as follows ..." after OK): the notice's text."""


def watcher(cam, notes: list, say):
    """set_row's `say`: its choice said as it is; a notice after OK kept in `notes`, not printed (it can name another
    setting's value), and when it reads "not available", left as a notice the kit does not answer is left (MENU, and its
    OK where the camera refuses MENU, as it does on these, and OK is its only button: camkit.live.leave_notice) and the
    row refused; an information screen after the choice kept too."""
    from camkit.live import leave_notice
    from mode_switch import text

    def watch(msg: str):
        if "notice after OK" in msg:
            t = " ".join(text(cam).split())
            notes.append(t)
            if re.search(r"not\s+available", t, re.I) and not safety.confirmation(t):
                leave_notice(cam)
                raise RefusedRow(t)
            say("   a notice after OK, closed with MENU (its text is in spotcheck.json)")
            return
        if "information after the choice" in msg:
            # set_row says the frame only; the screen's words are in events.jsonl (set_row_information)
            m = re.search(r"\(([^;()]+);", msg)
            how = "closed with MENU" if "closed with MENU" in msg else "taken with its OK"
            notes.append(f"an information screen after the choice ({m.group(1) if m else 'frame not said'}), {how}: "
                         "its words are in events.jsonl under set_row_information")
            say(f"   an information screen after the choice, {how}")
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
    # the slot screen reads as no known kind: its Enter goes by the run's --allow, consent to answer the row's own
    # screen (the shape check lifted, never the confirmation words), as the camera judges it too (answer_once)
    consent = f"--allow {MEMORY_ROW!r}"
    why, vouched = press_decision("enter!:Memory", "enter", highlighted(cam.frame.image, cam.frame.path), t, kind,
                                  False, tuple(allow), consent=consent)
    if why:
        raise Failed(f"Enter on slot {slot} refused: {why} ({cam.frame.path.name})")
    slot_frame = cam.frame.path.name
    cam.answer_once = consent
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
    """Back to the shooting screen, a download (camlink waits up to 5 s for the camera to allow it), and the menu's lock
    after it (camkit.session.wait_lock)."""
    from prove_run import to_shooting
    from proving.base import wait_lock
    from runner import close_screen
    close_screen(cam, link)
    to_shooting(link, hdmi, f"the download {tag}")
    got = link.download(tag)
    wait_lock(time.monotonic(), hdmi, clock=time)
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
    ap.add_argument("--aperture", action="store_true",
                    help="register every F-number the lens offers into the slot, each set through the SDK first "
                         "(prove_apertures), instead of the rows")
    ap.add_argument("--values", default=None, help="with --aperture: these F-numbers only (F x 100, comma-separated); "
                                                   "one the lens does not offer is said, never set")
    ap.add_argument("--fill-empty-slot", action="store_true",
                    help="with --aperture: register the slot even where it is empty in the start file, which fills it "
                         f"for good: the slot stays registered after the run, its values the start file's ("
                         f"{FILL_EMPTY_WORD})")
    ap.add_argument("--beyond-lens", action="store_true",
                    help="with --aperture: instead of the lens's F-numbers, try each F-number of the definition's table "
                         "the lens does not offer once through the same SDK set; one refused or read back otherwise is "
                         f"recorded in beyond_lens.json, never forced, nothing registered on it ({BEYOND_WORD})")
    a = ap.parse_args(argv)
    if a.fill_empty_slot and not a.aperture:
        sys.exit("memreg_run: --fill-empty-slot is the aperture run's (the owner's word for it): give it with --aperture")
    if a.beyond_lens and not a.aperture:
        sys.exit("memreg_run: --beyond-lens is the aperture run's: give it with --aperture")
    root = paths.run_root()
    doc = definitions.with_evidence(read_json(definitions.active()), definitions.active())
    if a.aperture:
        section = section_of(a.slot)
        print(f"--aperture: slot {a.slot} (set{section}): every F-number the attached lens offers (the SDK's list, read "
              f"at the run's start){f', among {a.values}' if a.values else ''}, each set through the SDK and read "
              f"back, then the slot registered and a download: {' and '.join(aperture_keys(section))} must hold it; "
              "the held one last; the live aperture put back and read back; the start file uploaded and checked")
        if a.fill_empty_slot:
            print(f"--fill-empty-slot: an empty slot is registered and stays registered afterwards, its values the "
                  f"start file's ({FILL_EMPTY_WORD})")
        if a.list:
            return 0
        if not memory_allowed(a.allow) or [x for x in a.allow if not memory_allowed([x])]:
            sys.exit(f"memreg_run: {MEMORY_ROW} is never-open (an action); --aperture opens it only with the owner's "
                     f"word, --allow {MEMORY_ROW!r}, and no other")
        return prove_apertures(a, doc, allowed_or_exit(a.allow))
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
