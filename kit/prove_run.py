"""Pass 2 on the camera: prove what each option writes. Choose it, OK, download the settings, diff.

    .venv/bin/python -u kit/prove_run.py --rows "Lens Compensation > Shading Comp." [--rows ...] [--limit N]

Jobs come from pass 1's map (kit2_pass1/map_all.json in the camera's runs/<model>_fw<fw>/, camkit.paths), limited
to the reviewed scope (kit2_pass1/pass2_scope_draft.json, "prove"). List rows and carousels' main options so far.

Per row: open the list and read which option the cursor opened on (the saved value). Proofs start
at the option after it and wrap round, so the last proof is the starting value and the row ends as
it began; that last diff must be empty, or the run stops. Per option:
  1. go to the row (MENU reopens at the row, or at the parent row inside a submenu), Right;
  2. check the list opened on the option the previous proof chose (the commit, seen on screen);
  3. step to the option by its known order, check its label under the cursor, OK;
  4. check the screen is back on the row, download, diff against the row's starting file.
A download closes the menu, and MENU sooner than ~4 s after one leaves the menu locked.
A list that offers a single option (Rec Frame Rate under PAL with XAVC HS 8K) cannot be proved by choosing: its
display proves it instead (prove_by_display), the option read by OCR and the vision model, nothing chosen, and the
value its row's records hold in the download the proof starts from (a proof line with "proof": "display").

Fails closed: any screen the proof did not expect (a warning, a confirmation) is cancelled with
MENU, never OK. The row is logged in failures.jsonl and skipped on later runs (--retry-failed);
if anything differs from the start file, the start file is uploaded and the restore checked, and
the run carries on with a new connection. Three failed rows in a row, a restore that does not
check out, or a STOP file end the run.

--allow LABEL (repeatable, as drive.py has it) lets a --rows run enter a never-open row the owner allowed in words, named
per row ("Audio Signal Volume"): a row whose path holds the label is proved even where the reviewed scope excludes it,
and the camera may open that label and no other never-open row; never the cards, Initialize, Reset Network Set. or
credentials. The run prints the rows allowed and each proof line carries "allowance": "the owner allowed <row>
remotely, <date>". A row the crawl never opened has no job (it is not in the map): pass 1 must map it first.

--network (with --rows) proves a Wi-Fi or Bluetooth setting a dated owner decision in the reviewed scope names
({"lifts": "network", "date", "rows", "why", "options": {"<row>": ["<option>"]}}: runner.network_decided_or_exit,
docs/decisions/0008), and only the options that decision names (network_jobs_or_exit): the others are said to stay by
hand. The run stops before anything connects when a decision names what none opens (credentials, identity, an action,
the serial number), when none of --rows holds a decided row, when a decided row names no option (it is opened to look
only), or when its job is not a list of options. The camera may open those rows and no other never-open row, never an
address screen, and chooses there only a named option (camkit.live); a row whose saved option is not named is left for
the session's upload to put back (RestoreAfter); no OK goes out on a screen nobody reads; the run asks local readers
only. Such a run prints and keeps no screen's text (KEPT): of an option under the cursor, only the map's own option
names ("shown", "vlm"); of a notice after OK, what safety.kept_screen keeps (its row labels and field names, the notice
as safety.notice_kept keeps it, the count withheld), in proofs.jsonl alone; a failure's quoted texts withheld; the
records that differ at the session's end by key alone; its folder owner-only (camkit.runs), checked at the end. Nothing
it says tells which option a network row was saved on: the named options are proved in their own order, each said as
"proof i of N", the records they changed said by key after them, and every such row ends with the session's upload of
the start file (NETWORK_RESTORE); the proofs' diffs against the start file tell it by nature, and stay in proofs.jsonl
in the run's owner-only folder. The reviewed scope's
"exclude" still keeps a row out; each proof line carries "allowance": "the owner decided on <date> that the kit may
open <row> remotely and choose <options>".

--info-ok "ROW=PHRASE" (repeatable, one row each, every one named with --rows and a label the definition or the map
knows: runner.info_ok_or_exit; PHRASE the notice's whole text as written, compared by its letters, digits and single
spaces, punctuation and glyphs ignored) proves a checklist that sits behind an information notice (the a1 II's Different
Set for Still/Mv): on each visit, after Right, the OK of the notice whose whole text is PHRASE is taken once
(proving.checklists.INFO_OK), only where proving.screens.pass_named_notice passes it (the lit bar before Right read as
the row; the phrase accounting for all of the notice but 10 letters or digits; no question mark, no confirmation,
nothing never-open, of identity or credentials; one button line, OK, lit; no other line naming a button, a choice or an
action, or on or below the OK's band), and each proof line carries "info_ok": {"row", "passed", "frame"}; a notice it
refuses fails the row with nothing pressed on it. A row with no map row of its own is mapped first:
kit/crawl_run.py --start-label ROW --limit 1 --info-ok ..., then pass1_labels.py, tiebreak.py and pass1_map.py --own,
and --map that map. Only for checklist jobs, and not with --network or --help-text.

Results: runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl, one line per option; frames and downloads numbered on.

The parts are in kit/proving/ (its __init__ lists them): the screen readers, the way to a row and back, the job
builders and the provers of the other row kinds (number fields, side lists, checklists, Creative Look's panels, White
Balance's grids, tables and keys). This file holds the list prover itself (prove_row, and prove_by_display for a list
of one option), the carousels' second axes (prove_axis_row), the session and main, and gives every name of those
parts under its old place (prove_run.option_key), which the walkers and provers import.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import camset, definitions, jsonl, models, ocr, paths, safety, screen  # noqa: E402
from camkit.vlm import PROMPTS  # noqa: E402,F401   (reread_proofs imports it from here)
from camkit.frames import OsdSource, eyes_from_config  # noqa: E402
from camkit.link import Link, StopRequested  # noqa: E402
from camkit.live import LiveCamera, lit_text, open_refused  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.screen import same_position  # noqa: E402
from camkit.session import check_restore, verify_restore  # noqa: E402
from crawl_run import go_to  # noqa: E402
from page_model import same_text  # noqa: E402
from runner import (EXIT_UNRESTORED, add_allow_argument, add_network_argument, add_scan_argument, allowed_or_exit,  # noqa: E402
                    changes_of, end_session, known_groups, known_labels, known_values, label_readings, load_scan,
                    log_network_decided, network_decided_or_exit, network_readings, network_values, read_json,
                    restoring, row_values, values_withheld)
from runner import add_info_ok_argument, definition, info_ok_or_exit, row_labels  # noqa: E402
# the run's settings live with their readers, and main() sets them there (proving.base.MAP, proving.jobs.HELP_TEXT,
# proving.sidelists.SPREAD); the tests point proving.base's and proving.tables' places at their own files
import proving.base  # noqa: E402
import proving.checklists  # noqa: E402
import proving.jobs  # noqa: E402
import proving.sidelists  # noqa: E402
import proving.tables  # noqa: E402,F401
# every name of the parts, under its old place (the walkers, the provers and the tests import them from here)
from proving.base import (AXES, LOCK_S, PASS1, Blocked, Failed, finish_attempt, frame_file, number,  # noqa: E402,F401
                          RestoreAfter, Tagged)
from proving.screens import (BAR_X, SEEN, _matches, ask_second, at_label, bar_text, carousel_text,  # noqa: E402,F401
                             closest_row, first_time_notice, glued, info_notice_ok, keeps_lead, main_name,
                             notice_focus, option_key, place, refuse_or_fail, run_tmp_png, same_place, strip_value,
                             vlm_option)
from proving.nav import (CYCLE, MODEL, after_download, cancel, enter_any, enter_path, enter_pp,  # noqa: E402,F401
                         find_row, move_to, shooting_like, to_row, to_shooting, where_in)
from proving.options import (by_place, by_position, closest_function, function_name, icon_bits,  # noqa: E402,F401
                             icon_index, option_index, same_functions, walk_row, which_option)
from proving.putback import mirrored_boxes, put_back_leftovers, say_put_back  # noqa: E402,F401
from proving.jobs import (APPROVED, COUPLED, EVERY_MAX, ICON_ROWS, KINDS, LABELS, OSD_ONLY, PP, PPS,  # noqa: E402,F401
                          axis_jobs, check_job, every_value, fields_job, iso_range_job, job_key, jobs,
                          look_base_jobs, look_jobs, planned, proof_key, sample_steps, scope_rows, side_job, wb_jobs)
from proving.fields import (box_bits, field_again, field_at, field_values, fields_by_reader,  # noqa: E402,F401
                            match_box, prove_fields_row, same_value, templates)
from proving.sidelists import (bar_ocr, by_neighbours, fix_lap, from_neighbours, prove_side_row,  # noqa: E402,F401
                               side_bits, side_index, side_templates, side_text, side_top, signed)
from proving.checklists import (CHECK_LATER, DISP_MODES, OK_RIGHT, box_text, check_box_label,  # noqa: E402,F401
                                check_state, focused_button, is_box, on_box, on_radio, prove_check_row,
                                radio_state, read_boxes, star_label)
from proving.looks import (LOOK_CODES, LOOK_PARAMS, look_cell, look_title, look_to_cell,  # noqa: E402,F401
                           look_value, open_look_panel, prove_look_base, prove_look_row)
from proving.wbgrid import WB_AXES, prove_wb_row, wb_reading  # noqa: E402,F401
from proving.tables import (HOLD, OWN_KINDS, SEPARATE_BOX, TICKED, cell_value, in_scope, key_jobs,  # noqa: E402,F401
                            leave_own_screen, near, own_screen, prove_table_row, sample_pickers, saved_index,
                            screen_of, separate_modes, separate_ticked, table_jobs, table_order, table_planned,
                            to_cell, to_key, to_ok, to_tile)
from proving.helptext import help_row  # noqa: E402,F401

# --context: the switched state this run proves in (pass 3), which a single-option list's display proof needs to tell
# which of its row's records holds the value now (display_records)
CONTEXT: str | None = None
# what a --network run keeps of a screen it withholds (safety.kept_screen): the row labels the kit knows (the decisions'
# rows among them), the values it knows, and the values by row label for a notice; set by main() on such a run
KEPT: dict = {"labels": set(), "values": set(), "by_row": {}}


# what every network row's proof ends with, whatever option the row was saved on: the session's upload of the start
# file puts it back (RestoreAfter), one text for every such row
NETWORK_RESTORE = "a network row's proofs end with the session's upload of the start file"


def kept_option(text, labels) -> str:
    """What a network row's proof keeps of an option read under the cursor (OCR's or the vision reader's): the text where
    it is one of the map's own option names for the row (`labels`, compared plain), else "(withheld)"."""
    names = {safety.plain(x) for x in labels or () if isinstance(x, str)}
    return text if isinstance(text, str) and safety.plain(text) and safety.plain(text) in names else "(withheld)"


def prove_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """Every option of one list row; returns the last download (equal to base_path's settings). Each proof carries
    the attempt's id; the attempt is recorded as finished (finish_attempt) only when the row ended as it began."""
    path, labels, kind = job["path"], job["labels"], job["kind"]
    attempt = f"{run.dir.name}-{time.time_ns():x}"
    n = len(labels)
    text = carousel_text if kind == "dialog" else bar_text
    base = camset.read(base_path)
    name = " > ".join(path)
    row_place = place(cam)
    history, put_back = [], None                   # each download's records differing from the start
    cam.press("right")
    if cam.read().kind != kind:
        refuse_or_fail(cam, name, f"not a {kind}")
    if n == 1 and kind == "list":
        # one option only (XAVC HS 8K's Rec Frame Rate under PAL): nothing to choose, so its display proves it
        return prove_by_display(cam, link, run, job, base_path, out, top, row_place, attempt)
    c = which_option(cam, job)
    if c is None:
        raise Failed(f"{name}: could not tell which option the {kind} opened on ({text(cam)!r})")
    order = [(c + i) % n for i in range(1, n)] + [c]
    choose = job.get("choose")          # a network row: only the options its decision names (network_jobs_or_exit)
    network_row = job.get("network_row")
    identity_row = job.get("network_class") == safety.LIFT_IDENTITY
    if choose is not None:
        order = [k for k in order if k in choose]
    if network_row:
        # nothing said tells which option the row was saved on: the named options are proved in their own order (never
        # the saved one last), the loop says "proof i of N" alone, and the session's upload of the start file always
        # ends the row (RestoreAfter, NETWORK_RESTORE). The proofs' diffs against the start file tell it by nature: they
        # stay in proofs.jsonl, in the run's owner-only folder (camkit.runs)
        order = sorted(set(order))
        print(f"{name}: proving {len(order)} named option(s) {[labels[k] for k in order]}; the saved value withheld, "
              "the start file put back by the session's upload", flush=True)
    else:
        print(f"{name}: saved value {labels[c]!r}; proving {[labels[k] for k in order]}", flush=True)

    def tell(message: str) -> None:
        """A line of the loop, said where the row is no network row's (its lines would tell the saved option)."""
        if not network_row:
            print(message, flush=True)
    keys = set()                        # a network row's: the records its proofs changed, said by key after the loop
    last, prev = base_path, c
    for step, k in enumerate(order):
        if step > 0:
            to_row(cam, path, top, row_place)
            if not same_place(place(cam), row_place):
                raise Failed(f"{name}: back at the row, the page or cursor row is not the one proved before")
            cam.press("right")
            if cam.read().kind != kind:
                raise Failed(f"{name}: Right opened {cam.read().kind}, not the {kind}")
            cur = which_option(cam, job)
            if cur != prev and network_row:
                # no index: after a refused proof the last OK "chose" the saved option, which nothing may tell
                raise Failed(f"{name}: the list did not open on the option the last OK chose")
            if cur != prev:
                raise Failed(f"{name}: the list opened on option {cur}, the last OK chose {prev} ({labels[prev]!r})")
        else:
            cur = c
        move_to(cam, cur, k, n, kind)
        if which_option(cam, job) != k:
            raise Failed(f"{name}: the cursor is not on {labels[k]!r} ({text(cam)!r})")
        chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)                   # evidence: the option under the cursor
        shown = text(cam)                              # as the camera shows it now (a carousel: with its axis value)
        if network_row:             # inside a network row only the map's own option names are kept (KEPT)
            shown, seen_vlm = kept_option(shown, labels), kept_option(seen_vlm, labels)
        cam.press("enter")
        if network_row:
            print(f"   proof {step + 1} of {len(order)}", flush=True)
        s = cam.read()
        notice, refused = None, False
        if s.kind == "notice":
            # an information notice after the choice applied (Sync Terminal = Always: "Enters the state
            # with Flash Effect dur Sht. applied", 2026-10-29): keep its text, close it with MENU (which
            # closes the menu too), never OK; the download shows what applied. A confirmation fails.
            # "Not available as follows <blocker>" refuses the choice (Flash Mode = Flash Off in Manual
            # Exposure, 2026-10-29): the proof says so and names the blocker; the value stays as it was.
            lines = ocr.read([cam.frame.path])[cam.frame.path]
            text_n = ocr.text_in(lines, (0, 0, 640, 480))
            why = safety.confirmation(text_n)
            if why:
                raise Failed(f"{name}: after OK on {labels[k]!r} a confirmation came up ({why}; {cam.frame.path.name})")
            refused = bool(re.search(r"not available|invalid", text_n, re.I))
            if network_row:
                # inside a network row no notice's text is kept or said: what safety.kept_screen keeps (its row labels
                # and field names; inside a Wi-Fi or Bluetooth setting the notice as safety.notice_kept keeps it, never
                # inside an identity row; the count withheld); MENU alone closes it
                kept = safety.kept_screen("notice" if not identity_row else "unknown", lines, KEPT["labels"],
                                          KEPT["values"], (), KEPT["by_row"])
                notice = {**kept, "frame": cam.frame.path.name}       # in proofs.jsonl alone (tell)
            else:
                notice = {"text": text_n, "frame": cam.frame.path.name}
                print(f"   {'refused' if refused else 'notice after OK'}: {text_n[:90]!r}", flush=True)
            cam.press("menu")
        elif s.kind == "shooting":
            # some choices close the menu (Focus Area = Wide went straight to the shooting screen with
            # the new area icon, 2026-10-29): the download shows what applied
            notice = {"text": "the menu closed after OK", "frame": cam.frame.path.name}
            tell("   the menu closed after OK")
        elif s.kind == "menu" and (same_place(place(cam), top) if top is not None else at_label(cam, "menu", path[0])):
            # back on the top-level row: XAVC HS 8K's Rec Frame Rate rebuilds Movie Settings on OK
            # (24p applied, 2026-10-31); the download shows what applied. Over the OSD there is no
            # recorded place for that row, so its label decides
            notice = {"text": "the camera went back to the menu page after OK", "frame": cam.frame.path.name}
            tell("   back on the menu page after OK")
        elif s.kind == "unknown" and not network_row and not same_place(place(cam), row_place):
            # an information screen without a notice's frame lines, "Don't show this again." over its
            # OK (Framing Stabilizer = On: Center, Movie mode, 2026-10-30): taken as the table prover
            # takes one, never ticking the box; anything else still fails the row. Inside a network row no OK goes
            # out on a screen nobody reads: the row fails, and MENU cancels it
            notice = info_notice_ok(cam, name)
        elif s.kind == "table" and not network_row and not same_place(place(cam), row_place):
            # an information screen with buttons after the choice (Exposure Ctrl Type = Flexible Exp. Mode: "Changes
            # keys assigned to suit this mode", a Custom Key/Dial Set. link beside its OK, 2026-11-07): its OK applies
            # the choice, and the download shows what else it rewrote; a confirmation fails the row
            notice = info_notice_ok(cam, name, kinds=("table",))
            if not same_place(place(cam), row_place):
                raise Failed(f"{name}: after the information's OK the screen is {cam.read().kind} "
                             f"({cam.frame.path.name}), not the row")
        elif not same_place(place(cam), row_place):
            raise Failed(f"{name}: after OK on {labels[k]!r} the screen is {s.kind} ({cam.frame.path.name}), not the row")
        back = cam.frame.path.name                     # the row showing its new value (or the notice)
        dat = link.download(f"{path[-1]}-{k}")
        done = time.monotonic()
        changes = camset.diff(base, camset.read(dat))
        history.append({ch.key: ch.after for ch in changes})
        rec = {"path": path, "kind": kind, "index": k, "label": labels[k], "shown": shown, "chosen_frame": chosen, "vlm": seen_vlm,
               "row_frame": back, "dat": dat.name, "base": base_path.name,
               "changes": changes_of(changes),
               "notice": notice, "applied": not refused, "attempt": attempt,
               # the class a network decision lifted the row from: the tools that read the proof's frames later keep
               # no reader's text of an identity row's (kit/tools/reread_proofs.py, kit/tools/reader_census.py)
               **({"network": job.get("network_class") or safety.LIFT_IDENTITY} if network_row else {})}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        brief = ", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:6]) or "no change"
        tell(f"   {labels[k]!r:24s} {brief}{' ...' if len(changes) > 6 else ''}")
        keys |= {ch.key for ch in changes}
        last, prev = dat, (cur if refused else k)
        after_download(cam, done)
        if k == c and changes and not network_row:
            put_back = put_back_leftovers(changes, history)
            if put_back is None:
                raise Failed(f"{name}: back on the saved value, {len(changes)} records still differ from the start")
            say_put_back(name, put_back)
    finish_attempt(run, attempt, name, put_back)
    if network_row:
        # the options in their own order and the records by key alone, never which changed what; then the session's
        # upload of the start file, whatever the row was saved on
        print(f"   proved {[labels[k] for k in order]}: records {sorted(keys)}", flush=True)
        raise RestoreAfter(f"{name}: {NETWORK_RESTORE}")
    if choose is not None and c not in choose:
        # the saved option is not one the decision lets the kit choose: the session's upload puts it back
        raise RestoreAfter(f"{name}: its saved option is not one the decision names; the session's upload puts it back")
    to_row(cam, path, top, row_place)
    return last


def display_records(settings: list, path: list, context: str | None) -> list:
    """The records a single-option list's value is in now: of the definition's settings proved through this row (their
    "proved" menu rows, "Row > Row [context]"), those whose proof context is wholly part of the run's (--context) and
    names the most of it. Under "Movie mode, PAL, File Format XAVC HS 8K" the 8K rate's own record (proved in "Movie
    mode, File Format XAVC HS 8K") is chosen over the 4K one proved in "Movie mode" alone, and over the rate proved
    with no context; the HS 4K rate's (proved under "File Format XAVC HS 4K") is not part of the run's state at all.
    Ties are all kept: each holds the value as much as the other. [] when none was proved through the row."""
    row = " > ".join(path)
    here = {w.strip() for w in (context or "").split(",") if w.strip()}
    score = {}
    for s in settings:
        for m in (s.get("proved") or {}).get("menu") or []:
            name, _, ctx = m.partition(" [")
            words = {w.strip() for w in ctx.rstrip("]").split(",") if w.strip()}
            if name == row and words <= here:
                score[s["key"]] = max(score.get(s["key"], -1), len(words))
    best = max(score.values(), default=None)
    return sorted(k for k, n in score.items() if n == best)


DISPLAY_KEY = re.compile(r"(global|set(\d+)):0x([0-9a-f]+)(?:\[(\d+)\])?")


def held_value(cs, key: str):
    """The value a definition key ("global:0x0202", "set1:0x0202", "global:0x04e9[3]" for one slot) holds in a
    settings file; None when the file has no such record."""
    m = DISPLAY_KEY.fullmatch(key)
    if not m:
        return None
    rec = cs.get(int(m[2]) if m[2] else 0, int(m[3], 16))
    if rec is None:
        return None
    if m[4] is not None:
        vals = rec.values()
        return vals[int(m[4])] if int(m[4]) < len(vals) else None
    return rec.value()


def display_proof(job: dict, ocr_text: str, vlm_text: str, base_path: Path, held: dict, frames: tuple,
                  attempt: str) -> dict:
    """A single-option list's proof line, kind "list" with "proof": "display": the option's label, as the map has it,
    and both readings of the screen (the OCR and the vision model must both name it), and the values its row's records
    hold in the download the proof starts from ("held", [{"key", "value"}]), which is "dat" and "base" both: nothing
    is chosen, so nothing changes. kit/pass2_report.py takes each held value as the one that label writes."""
    label = job["labels"][0]
    for reader, t in (("OCR", ocr_text), ("the vision model", vlm_text)):
        if not _matches(t, [label]):
            raise Failed(f"{' > '.join(job['path'])}: the only option should read {label!r}, {reader} read {t!r}")
    if not held:
        raise Failed(f"{' > '.join(job['path'])}: no record of the definition was proved through this row in a state "
                     f"like this one ({CONTEXT or 'no context'}): prove it by choosing where it offers two options first")
    chosen, back = frames
    return {"path": job["path"], "kind": "list", "proof": "display", "index": 0, "label": label, "shown": ocr_text,
            "chosen_frame": chosen, "vlm": vlm_text, "row_frame": back, "dat": base_path.name, "base": base_path.name,
            "held": [{"key": k, "value": v} for k, v in held.items()], "changes": [], "notice": None, "applied": True,
            "attempt": attempt}


def prove_by_display(cam, link, run, job, base_path: Path, out, top, row_place, attempt: str) -> Path:
    """A list that opens with a single option: the option is read off the screen (OCR and the vision model), MENU
    leaves the list with nothing chosen, and the values the row's records hold in base_path (display_records, from
    the definition of the camera the kit works on) make one proof line (display_proof). No OK, no download."""
    path, name = job["path"], " > ".join(job["path"])
    s = cam.read()
    if s.count not in (None, 1):
        cancel(cam, link)
        raise Failed(f"{name}: the map has one option, the list on screen {s.count}: map the row again")
    shown, seen_vlm, chosen = bar_text(cam), vlm_option(cam), cam.frame.path.name
    cancel(cam, link)                           # MENU: out of the list, nothing chosen
    back = cam.frame.path.name
    target = definitions.active(required=False)
    settings = definitions.with_evidence(read_json(target), target)["settings"] if target is not None and target.exists() else []
    cs = camset.read(base_path)
    held = {k: v for k in display_records(settings, path, CONTEXT) if (v := held_value(cs, k)) is not None}
    rec = display_proof(job, shown, seen_vlm, base_path, held, (chosen, back), attempt)
    if job.get("network_row"):          # a network row's: only the map's own option names (KEPT)
        rec["shown"], rec["vlm"] = kept_option(rec["shown"], job["labels"]), kept_option(rec["vlm"], job["labels"])
    out.write(json.dumps(rec) + "\n")
    out.flush()
    print(f"{name}: one option, {rec['label']!r} (OCR {rec['shown']!r}, vision model {rec['vlm']!r}), held in "
          f"{', '.join(held)}", flush=True)
    finish_attempt(run, attempt, name)
    to_row(cam, path, top, row_place)
    return base_path


def axis_title(cam) -> str:
    time.sleep(0.4)                               # the title redraws after the strip
    cam.refresh("reread")
    return carousel_text(cam)


def axis_at(cam, vals) -> int | None:
    """The axis value on the title: exactly, else the longest value inside the reading ("Custom 3 7":
    an icon read as a character after the name, 2026-10-29); else the vision model's, else the strip's lit cell
    (axis_reading, which says how too). None when none names one."""
    return axis_reading(cam, vals)[0]


def axis_reading(cam, vals) -> tuple:
    """(the axis value's index or None, how it was read): the title, exactly, else the longest value inside the reading
    ("Custom 3 7": an icon read as a character after the name, 2026-10-29), else the vision model's reading, how {} for
    each; else the strip's lit cell, its short text ("C3") or its neighbours' (proving.screens.strip_value: only while
    the title still reads as the option's; "Customß 7", the Custom 3 box's corner over the title, 2026-11-08 and
    2026-11-09), how then {"read_by": "axis cell", "cell_readings": [...]}, which a proof carries."""
    t = axis_title(cam)
    hits = [i for i, v in enumerate(vals) if option_key(v) == option_key(t)]
    if len(hits) == 1:
        return hits[0], {}
    inside = [i for i, v in enumerate(vals) if option_key(v) and option_key(v) in option_key(t)]
    if inside:
        best = max(len(option_key(vals[i])) for i in inside)
        top = [i for i in inside if len(option_key(vals[i])) == best]
        if len(top) == 1:
            return top[0], {}
    v = vlm_option(cam)                          # OCR could not tell: the vision model's reading
    vh = [i for i, x in enumerate(vals) if option_key(x) == option_key(v)] if v else []
    if len(vh) == 1:
        return vh[0], {}
    return strip_value(cam, vals, t, v)          # neither: the strip's lit cell, while the title is the option's


# --first: per axis job ("Drive Mode / Self-timer(Cont.)"), the value to choose before its proofs. An axis proof
# proves every value against the one held, which is itself never proved; from another value, it is.
FIRST: dict = {}


def first_values(given: list) -> dict:
    """--first's arguments as FIRST holds them, {"ROW / OPTION": "VALUE"}; one without " / " in the job's name or with
    no value after "=" is refused (SystemExit), before anything is sent to the camera."""
    out = {}
    for f in given or []:
        key, _, value = f.partition("=")
        if not value.strip() or " / " not in key:
            sys.exit(f"--first {f!r}: ROW / OPTION=VALUE")
        out[key.strip()] = value.strip()
    return out


def prove_axis_row(cam, link, run, job, base_path: Path, out, top=None) -> Path:
    """One carousel option's second axis: every value (Right/Left the short way round, axes wrap),
    OK, download, diff. The option is found by its title being one of its axis values ("Custom 2"
    is still the Custom option). The last visit puts the axis back on the value it held and the
    carousel back on the option it opened on; that diff must be empty."""
    path, vals = job["path"], job["values"]
    name, n = f"{path[0]} / {job['option']}", len(vals)
    base = camset.read(base_path)
    row_place = place(cam)
    last, order, a0, prev, saved, downs0, rebase = base_path, None, None, None, None, 0, None
    while True:
        if order is not None:
            to_row(cam, path, top, row_place)
            if not same_place(place(cam), row_place):
                raise Failed(f"{name}: back at the row, the page or cursor row is not the one proved before")
        cam.press("right")
        if cam.read().kind != "dialog":
            raise Failed(f"{name}: Right opened {cam.read().kind}, not the carousel")
        if order is None:
            saved = axis_title(cam)
        downs = 0
        for _ in range(40):
            if axis_at(cam, vals) is not None:
                break
            cam.press("down")
            downs += 1
        else:
            raise Failed(f"{name}: the carousel never showed one of {vals[:3]}")
        cur = axis_at(cam, vals)
        if order is None:
            a0, downs0 = cur, downs
            order = [i for i in range(n) if i != a0] + [a0]
            first = FIRST.get(name)
            if first is not None:
                k0 = [i for i, v in enumerate(vals) if option_key(v) == option_key(first)]
                if len(k0) != 1:
                    raise Failed(f"{name}: --first {first!r} is not one of its values {vals}")
                if k0[0] != a0:
                    # chosen first, then every value against it (the one it held included), then back to it
                    rebase, order = k0[0], [k0[0]] + [i for i in range(n) if i != k0[0]] + [k0[0]]
            print(f"{name}: holds {vals[a0]!r}; proving {[vals[i] for i in order]}", flush=True)
        elif cur != prev:
            raise Failed(f"{name}: the axis shows {vals[cur] if cur is not None else None!r}, the last OK chose {vals[prev]!r}")
        k = order.pop(0)
        d = (k - cur) % n
        key, steps = ("right", d) if d <= n - d else ("left", n - d)
        for _ in range(steps):
            cam.press(key)
            if cam.read().kind != "dialog":
                raise Failed(f"{name}: {key} on the axis left the carousel ({cam.read().kind})")
        got, how = axis_reading(cam, vals)
        if got != k:
            raise Failed(f"{name}: the axis is not on {vals[k]!r} ({axis_title(cam)!r})")
        final = not order
        if final:                                   # back to the option the carousel opened on
            for _ in range(downs0):
                cam.press("up")
            if option_key(axis_title(cam)) != option_key(saved):
                raise Failed(f"{name}: back up {downs0}, the carousel shows {axis_title(cam)!r}, not {saved!r}")
        chosen, shown, seen_vlm = cam.frame.path.name, axis_title(cam), vlm_option(cam)
        cam.press("enter")
        s = cam.read()
        notice, refused = None, False
        if s.kind == "notice":
            text_n = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
            if safety.confirmation(text_n):
                raise Failed(f"{name}: after OK a confirmation came up ({cam.frame.path.name})")
            refused = bool(re.search(r"not available|invalid", text_n, re.I))
            notice = {"text": text_n, "frame": cam.frame.path.name}
            print(f"   {'refused' if refused else 'notice after OK'}: {text_n[:90]!r}", flush=True)
            cam.press("menu")
        elif s.kind == "shooting":
            notice = {"text": "the menu closed after OK", "frame": cam.frame.path.name}
        elif not same_place(place(cam), row_place):
            raise Failed(f"{name}: after OK the screen is {s.kind} ({cam.frame.path.name}), not the row")
        dat = link.download(f"{path[0]}-axis-{k}")
        done = time.monotonic()
        changes = camset.diff(base, camset.read(dat))
        rec = {"path": path, "kind": "axis", "option": job["option"], "index": k, "label": vals[k], "shown": shown,
               "final": final, "chosen_frame": chosen, "vlm": seen_vlm, **how, "row_frame": cam.frame.path.name, "dat": dat.name,
               "base": base_path.name, "notice": notice, "applied": not refused,
               "changes": changes_of(changes)}
        out.write(json.dumps(rec) + "\n")
        out.flush()
        brief = ", ".join(f"{ch.key} {ch.before!r}->{ch.after!r}" for ch in changes[:6]) or "no change"
        print(f"   {vals[k]!r:40s} {brief}{' ...' if len(changes) > 6 else ''}", flush=True)
        last = dat
        after_download(cam, done)
        if rebase is not None and k == rebase and not final and not refused:
            # the state --first asked for: from here the proofs are against it, and the carousel now opens on it
            base_path, base, a0, saved, downs0, rebase = dat, camset.read(dat), k, shown, 0, None
            print(f"   proofs from here are against {vals[k]!r}", flush=True)
        if final:
            if changes:
                raise Failed(f"{name}: axis and option back, {len(changes)} records still differ")
            break
        prev = cur if refused else k
    to_row(cam, path, top, row_place)
    return last


class OsdEyes(OsdSource):
    """The SDK's OSD image as the eyes, for rows that can take the menus off HDMI (HDMI Info.
    Display, HDMI Resolution ...; user, 2026-10-28: "items we can't get over hdmi we can pull over
    screen grabs"). Same calls as HdmiSource."""
    timing: dict = {}

    def grab(self, tag="f", save=True):
        return super().grab(tag) if save else self.peek()

    def settle(self, before, tag="f", expect_change=None, sent_at=None, **kw):
        return super().settle(before, tag, expect_change)

    def close(self):
        pass


def end_rows(link, eyes, start: Path, reach, withheld: bool | None = None):
    """A proof session's end (runner.end_session: the shooting screen, the download, the start file put back when anything
    differs); withheld (a --network run, whose decided rows main() gives proving.jobs.NETWORK, unless said): the records
    that differ said by their keys alone (runner.values_withheld)."""
    withheld = bool(proving.jobs.NETWORK) if withheld is None else withheld
    return end_session(link, eyes, start, "the settings download after the rows", reach=reach,
                       **values_withheld(withheld))


def put_start_back(run, hdmi, ref: Path, withheld: bool = False) -> bool:
    """A run before this one can stop short of its restore (a crash, 2026-10-29), and a context run
    starts from a file of its own: if the camera differs from `ref`, upload it, wait for the camera
    to restart, reconnect and check (an upload ends the session, 2026-10-30). True when it matches. withheld: a
    --network run, whose check says the records that differ by their keys alone (runner.values_withheld)."""
    with Link(run) as link:
        hdmi.attach(link)
        if screen.read(hdmi.grab(save=False)).kind in ("menu", "tiles"):
            link.press("menu", cleanup=True)
            time.sleep(1.0)
        to_shooting(link, hdmi, "the check of the start file")
        ch = camset.diff(camset.read(ref), camset.read(link.download("start-check")))
        if not ch:
            return True
        print(f"the camera differs from {ref.name} in {len(ch)} records {[c.key for c in ch][:6]}: uploading it",
              flush=True)
        print(link.upload(ref), flush=True)
    return verify_restore(run, ref, **values_withheld(withheld)) == 0


def session(link, hdmi, run, cycle, model, pending, start, out, failures) -> str:
    """One connection: prove rows from `pending` (removing them) until done, a row fails, or STOP.
    Always ends on the shooting screen. Returns "done", "failed", "stop" or "error"."""
    cam = LiveCamera(link, hdmi, run, may_open={r.split(" > ")[-1] for r in APPROVED
                                                if safety.owner_may_approve(safety.never_open(r.split(" > ")[-1]))}
                     | proving.jobs.ALLOWED, network=proving.jobs.NETWORK, options=proving.jobs.NETWORK_OPTIONS,
                     values=network_values(proving.jobs.NETWORK, MODEL) if proving.jobs.NETWORK else None,
                     readings=network_readings(proving.jobs.NETWORK, MODEL) if proving.jobs.NETWORK else None,
                     labels=label_readings(MODEL) if proving.jobs.NETWORK else None)
    status = "done"
    try:
        cam.press("menu")
        if cam.read().kind == "shooting":
            # MENU within a few seconds of a download is locked (section 8 of the playbook): once more after a wait
            time.sleep(LOCK_S)
            cam.press("menu")
        if cam.read().kind == "menu" and cam.read().focus == "groups":
            # the menu reopens where a hand left it, the focus in the group column: Right moves it onto the
            # page's rows, which is where every scan position is (it chooses nothing). Only with the menu at
            # rest (cam.press waits out the slide): on a row, Right opens it (2026-11-06). A never-open group
            # left lit in the column (Accessibility, the Screen Reader's; failed attempts left the cursor on
            # it, 2026-11-07) is stepped off first, since Right is refused on it; so is one whose name reads one letter
            # off a never-open group's or action's name ("FTP Transter", safety.group_refused, 2026-11-13), and no
            # Right goes out while the lit group is one of those or the screen no longer reads as the group column
            known = known_groups(model)

            def refused() -> str:
                lit = lit_text(cam.frame.image, cam.frame.path)
                return open_refused(lit, cam.may_open) or safety.group_refused(lit, known) or ""
            for key in ("up", "down", "down"):
                if not refused():
                    break
                cam.press(key)
            if refused() or cam.read().kind != "menu" or cam.read().focus != "groups":
                raise Failed("the menu reopened in the group column, and no group lit there may be stepped into (or "
                             "the screen no longer reads as the column): no Right; closed with MENU")
            cam.press("right")
            if cam.read().kind not in ("menu", "tiles"):
                # Right opened something after all: MENU cancels it (it chose nothing), and the session stops
                # here rather than walk from a screen the scan does not know
                cam.press("menu")
                raise Failed(f"Right to step into the rows opened a {cam.read().kind} screen instead; cancelled")
        j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
        if j is None:
            raise Failed(f"the menu opened on a screen the scan does not know ({cam.read().kind})")
        last = start
        while pending:
            job = pending[0]
            try:
                j = go_to(cam, cycle, model, j, job["path"][0])
                for _ in range(job.get("nth", 0)):          # the next row with the same label (movie keys)
                    if j is None:
                        break
                    cam.press("down")
                    j = (j + 1) % len(cycle)
                    if not same_position(cam.read(), cycle[j]["screen"]):
                        j = None
                if j is None:
                    raise Failed(f"on the way to {job['path'][0]!r} a screen was not the one the scan recorded")
                top = place(cam)
                enter_any(cam, job["path"], 0)
                prove = help_row if proving.jobs.HELP_TEXT else \
                    {"fields": prove_fields_row, "sidelist": prove_side_row, "checklist": prove_check_row,
                     "axis": prove_axis_row, "look": prove_look_row, "lookbase": prove_look_base,
                     "wbgrid": prove_wb_row, "table": prove_table_row}.get(job["kind"], prove_row)
                if job.get("eyes") == "osd":
                    # at the row over HDMI; the proof itself watches the OSD (its choices can change HDMI),
                    # and from there top is wherever MENU reopens over the OSD
                    cam.hdmi = OsdEyes(link, run)
                    cam.refresh("osd-eyes")
                    top = None
                try:
                    last = prove(cam, link, run, job, last, out, top)
                except Blocked as b:
                    print(f"row blocked: {b}", flush=True)
                    failures.write(json.dumps({"path": job["path"], "why": str(b), "blocked": b.reason,
                                               "frame": cam.frame.path.name,
                                               **({"kind": job["kind"], "option": job["option"]}
                                                  if job["kind"] in ("axis", "table") else {})}) + "\n")
                    failures.flush()
                finally:
                    if cam.hdmi is not hdmi:
                        cam.hdmi = hdmi
                        time.sleep(1.0)
                        cam.refresh("hdmi-eyes")
                for _ in range(len(job["path"]) + 2):       # back up to the top-level row
                    if cam.read().kind != "submenu":
                        break
                    cam.press("left")
                if cam.read().kind == "submenu":
                    # Left does nothing on some pages: Monitor Brightness, with its test chart, took
                    # ~39,000 Lefts overnight (2026-11-01). The row's results are written: cancel out
                    raise Failed(f"Left does not leave the {job['path'][0]!r} page")
                if cam.read().kind == "dialog":             # out of the PP panel: the carousel; MENU cancels it
                    cam.press("menu")
                    # after a heavy profile change the camera can ignore MENU for a while (PP6 Gamma,
                    # 2026-10-29): look at fresh frames, and press again only while the carousel stays
                    for _ in range(8):
                        if cam.read().kind != "dialog":
                            break
                        time.sleep(2.5)
                        if cam.refresh("menu-wait").kind == "dialog":
                            cam.press("menu")
                if not same_position(cam.read(), cycle[j]["screen"]):
                    raise Failed(f"back on {job['path'][0]!r}, the row does not look as the scan recorded it")
            except RestoreAfter as e:
                print(f"row done, left for the restore: {e}", flush=True)
                pending.pop(0)
                status = "restore"
                break
            except Failed as e:
                # inside a network row a failure's quoted texts (a screen's, an option's) are withheld
                why = safety.quoted_withheld(e) if job.get("network_row") else str(e)
                print(f"row failed: {why}; cancelling", flush=True)
                failures.write(json.dumps({"path": job["path"], "why": why, "frame": cam.frame.path.name,
                                           **({"kind": job["kind"], "option": job["option"]}
                                              if job["kind"] in ("axis", "table") else {})})
                               + "\n")
                failures.flush()
                pending.pop(0)
                status = "failed"
                break
            pending.pop(0)
    except StopRequested:
        print("STOP file: cancelling", flush=True)
        status = "stop"
    except Failed as e:
        print(f"stopped: {safety.quoted_withheld(e) if proving.jobs.NETWORK else e}", flush=True)
        status = "error"
    except Exception as e:
        said = f"{type(e).__name__}: {e}"
        print(f"error: {safety.quoted_withheld(said) if proving.jobs.NETWORK else said}; cancelling", flush=True)
        status = "error"
    try:
        cancel(cam, link)
    except RuntimeError as e:                # the HDMI feed is gone: cancel looking through the OSD
        print(f"   HDMI: {e}; cancelling through the OSD", flush=True)
        cam.hdmi = OsdEyes(link, run)
        cam.refresh("osd-cancel")
        cancel(cam, link)
    if cam.read().kind in ("menu", "tiles", "submenu"):
        link.press("menu", cleanup=True)
    return status


def network_rows_or_exit(rows: list) -> tuple:
    """--network for the rows named with --rows: ({row: date} of the Wi-Fi and Bluetooth settings a dated owner decision
    in the reviewed scope names and some label of --rows' paths is (safety.network_lifted: never an address screen,
    which only drive.py opens), {row: [the options the decision lets the kit choose]}, the words each proof line's
    allowance carries for them). Stops before anything connects when the decisions name what none opens
    (runner.network_decided_or_exit), when none of --rows holds such a row, or when one of them is opened to look only
    (no option named: nothing to prove by choosing)."""
    decided, options, _ = network_decided_or_exit()
    settings = {r: d for r, d in decided.items() if not safety.address_screen(r)}
    named = {r: d for r, d in settings.items()
             if any(safety.network_lifted(label, {r: d}) for p in rows for label in p.split(" > "))}
    if not named:
        sys.exit("--network: none of the rows named with --rows is a Wi-Fi or Bluetooth setting the decision names "
                 f"({', '.join(settings) or 'it names only address screens, which only drive.py opens'}): nothing was "
                 "sent to the camera")
    looks = [r for r in named if not options.get(r)]
    if looks:
        sys.exit(f"--network: the owner's decision opens {', '.join(map(repr, looks))} to look only: a proof chooses an "
                 "option, so it proves only options the decision names (\"options\": {\"<row>\": [\"<option>\"]}, "
                 "docs/decisions/0008); nothing was sent to the camera")
    chosen = {r: options[r] for r in named}
    return named, chosen, safety.network_allowance(named, chosen)


def network_jobs_or_exit(todo: list, named: dict, options: dict) -> list:
    """The jobs of a --network run, each one whose path holds a row a network decision opens (named) marked with that
    row ("network_row") and the indices of its options the decision names ("choose", as the map labels them, compared
    folded: safety.plain); the others are said to stay by hand. Stops before anything connects for such a job that is
    not a list of options (a carousel's second axis, number fields, a panel: Right, Left or a dial would commit there)
    or for an option the decision names that the map's labels do not hold."""
    for j in todo:
        row = next((r for label in j["path"] for r in [safety.network_lifted_row(label, named)] if r), None)
        if row is None:
            continue
        if j["kind"] != "list":
            sys.exit(f"--network: {job_key(j)!r} is a {j['kind']} job, and a row a network decision opens is proved "
                     "only as a list of options (anything else can commit an option with Right, Left or a dial): "
                     "nothing was sent to the camera")
        want = {safety.plain(o): o for o in options.get(row) or ()}
        have = {safety.plain(lab): i for i, lab in enumerate(j["labels"])}
        lost = [o for k, o in want.items() if k not in have]
        if lost:
            sys.exit(f"--network: the decision names {', '.join(map(repr, lost))} for {row!r}, which pass 1's map does "
                     f"not list among its options ({', '.join(map(repr, j['labels']))}): nothing was sent to the camera")
        j["network_row"], j["choose"] = row, sorted(have[k] for k in want)
        j["network_class"] = next(c for label in j["path"] if safety.network_lifted_row(label, named)
                                  for c in [safety.lift_class(label)])
        by_hand = [lab for i, lab in enumerate(j["labels"]) if i not in j["choose"]]
        if by_hand:
            print(f"{job_key(j)}: proving {', '.join(want.values())}; by hand: {', '.join(by_hand)} (the decision names "
                  "no other option)", flush=True)
    return todo


def info_ok_jobs_or_exit(todo: list, named: dict) -> None:
    """--info-ok passes a notice before a checklist only (proving.checklists.INFO_OK): stops before anything connects
    when a row it names (`named`) is proved as another kind of job."""
    other = sorted({r for r in named for j in todo
                    if safety.plain(" > ".join(j["path"])) == safety.plain(r) and j["kind"] != "checklist"})
    if other:
        sys.exit(f"--info-ok passes a notice before a checklist only: {', '.join(map(repr, other))} is proved as "
                 "another kind")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", action="append", default=None, help="prove only these rows (path with ' > ')")
    add_allow_argument(ap)
    add_network_argument(ap)
    add_info_ok_argument(ap)
    ap.add_argument("--limit", type=int, default=None, help="stop after this many rows")
    ap.add_argument("--list", action="store_true", help="print the rows and options the run would prove, then stop (no camera)")
    ap.add_argument("--retry-failed", action="store_true", help="include rows that failed in earlier runs")
    ap.add_argument("--redo", action="store_true",
                    help="with --rows: prove the named rows' options again, proved before or not (the report takes "
                         "the latest proof per option: a cell whose earlier proofs carry a side effect of the way in, "
                         "the Dial/Wheel box ticked after the base was taken, 2026-11-07)")
    add_scan_argument(ap)
    ap.add_argument("--run", default="kit2_pass2", help="run folder in the camera's runs/<model>_fw<fw>/")
    ap.add_argument("--map", default=None, type=paths.run_arg,
                    help="a pass-3 run's map.json instead of pass 1's (no axis jobs then): kit2_crawl/map.json is "
                         "in the camera's runs/<model>_fw<fw>/")
    ap.add_argument("--looks", action="store_true", help="prove Creative Look's parameter panels (18 looks x 8)")
    ap.add_argument("--look-base", action="store_true", help="prove the six custom looks' base look (12 looks each)")
    ap.add_argument("--every", action="store_true",
                    help="side lists and number fields: every value, not the lowest, middle and highest (scales of up "
                         "to 64 values), to check that a family's straight line holds at every step")
    ap.add_argument("--spread", action="store_true",
                    help="side lists: lowest, middle and highest only (a long text list: first, middle, last)")
    ap.add_argument("--look-in-use", action="store_true",
                    help="--looks: the start file makes the job's look the one in use, and the carousel opens on it: "
                         "go straight in (a custom look whose base was changed by a file has no pass-1 icon)")
    ap.add_argument("--start", default=None, type=paths.run_arg,
                    help="the settings file the run must start from: if the camera differs, it is uploaded first "
                         "(kit2_pass2/dat/NNNNN_start.DAT is in the camera's runs/<model>_fw<fw>/)")
    ap.add_argument("--context", default=None, help="the switched state these proofs are made in (pass 3)")
    ap.add_argument("--first", action="append", default=None, metavar="ROW / OPTION=VALUE",
                    help="an axis job: choose this value first and prove from it, so the value it held is proved too "
                         "(the run's start file still goes back on at the end)")
    ap.add_argument("--pp", default=None, help="comma-separated profiles for the PP side lists (default PP1), "
                                               "e.g. PP2,PP3,PP4,PP5,PP6,PP10,PP11")
    ap.add_argument("--wb", action="store_true", help="prove White Balance's fine-tune grids (14 presets x 2 axes)")
    ap.add_argument("--picker-sample", action="store_true",
                    help="with --tables: prove each shared function list in full on its first slot only, and three "
                         "functions on the other slots")
    ap.add_argument("--tables", action="store_true",
                    help="prove the cells kit/table_walk.py walked (Image Quality Settings, My Dial Settings, "
                         "Fn Menu Settings)")
    ap.add_argument("--wb-corners", action="store_true", help="every preset's grid at its four corners (both axes at their ends)")
    ap.add_argument("--help-text", action="store_true",
                    help="read the camera's help (In-Camera Guide) for each list / dialog row and option instead of "
                         "proving: <run>/option_help.jsonl in the camera's runs; nothing is chosen")
    ap.add_argument("--eyes", choices=["hdmi", "osd", "osd-all"], default="hdmi",
                    help="osd: also prove the rows that can take the menus off HDMI, watching their proofs "
                         "through the SDK's OSD image (the way there is still over HDMI); osd-all: the whole "
                         "run through the OSD, for rows that change the HDMI signal itself (frame rate, "
                         "resolution: the capture may not come back until the restore)")
    a = ap.parse_args()
    if a.allow and not a.rows:
        sys.exit("--allow opens a never-open row for the rows named with --rows only")
    if a.network and not a.rows:
        sys.exit("--network opens a Wi-Fi or Bluetooth setting for the rows named with --rows only")
    if a.network and (a.help_text or a.looks or a.look_base or a.wb or a.wb_corners or a.tables):
        sys.exit("--network proves a Wi-Fi or Bluetooth setting's list options only: not with --help-text, --looks, "
                 "--look-base, --wb, --wb-corners or --tables")
    if a.info_ok and not a.rows:
        sys.exit("--info-ok passes a notice for the checklist rows named with --rows only")
    if a.info_ok and a.network:
        sys.exit("--info-ok passes no notice on a --network run: its rows are looked at, or chosen in, only")
    if a.info_ok and a.help_text:
        sys.exit("--info-ok passes no notice with --help-text, which reads the help and passes none")
    allowance = allowed_or_exit(a.allow)
    proving.jobs.ALLOWED.update(a.allow)
    network = {}
    if a.network:
        network, chosen, words = network_rows_or_exit(a.rows)
        proving.jobs.NETWORK.update(network)
        proving.jobs.NETWORK_OPTIONS.update(chosen)
        allowance = "; ".join(x for x in (allowance, words) if x)
    proving.jobs.HELP_TEXT = a.help_text            # before jobs(): help reads rows proofs leave out
    proving.jobs.OSD_ROWS = a.eyes in ("osd", "osd-all")
    if a.eyes == "osd-all" and a.start:
        sys.exit("--eyes osd-all takes the camera's settings at the start as its start file (no --start)")
    if a.pp:
        PPS[:] = a.pp.split(",")
    if a.map:
        proving.base.MAP = Path(a.map)
    if a.info_ok:              # a row named by a label the definition or the map knows, before anything connects
        mapped = read_json(proving.base.MAP).get("rows") if Path(proving.base.MAP).exists() else []
        known = row_labels(definition()) | {x for r in mapped or [] for x in r.get("path") or [] if isinstance(x, str)}
        proving.checklists.INFO_OK.update(info_ok_or_exit(a.info_ok, a.rows, labels=known))
    body = models.current(Run(a.run).root)
    if body is None:
        sys.exit("no settings file downloaded yet tells which camera this is: run pass 1 (or any download) first")
    if body != models.A1II:
        # the label sequences and record ids below were proved on the ILCE-1M2: another body's rows use its own map
        print(f"camera {body}: the ILCE-1M2's own label tables are left out", flush=True)
        LABELS.clear()
        ICON_ROWS.clear()
        DISP_MODES.clear()
    todo = jobs(set(a.rows) if a.rows else None) + ([] if a.map else axis_jobs(set(a.rows) if a.rows else None))
    if a.every:
        todo = every_value(todo)
    FIRST.update(first_values(a.first))
    global CONTEXT
    proving.sidelists.SPREAD, CONTEXT = a.spread, a.context
    if a.looks:
        todo = [j for j in todo if j["kind"] == "look"] + look_jobs()
        if a.look_in_use:
            if not a.rows:
                sys.exit("--look-in-use goes straight into the look in use: name that one panel with --rows")
            todo = [{**j, "in_use": True} for j in todo]
    if a.look_base:
        todo = look_base_jobs()
    if a.wb:
        todo = wb_jobs()
    if a.tables:
        todo = table_jobs(set(a.rows) if a.rows else None)
        if a.picker_sample:
            todo = sample_pickers(todo)
    if a.wb_corners:                                 # every preset's four corners (the axes alone: --wb)
        todo = [{**j, "corners": True, "only_corners": True, "option": f"grid {j['preset']} corners"} for j in wb_jobs()]
    # one preset or look: --rows "White Balance / grid 11 corners", "Creative Look / panel 17", "Creative Look / base 12"
    if a.rows and (a.wb or a.wb_corners or a.looks or a.look_base):
        todo = [j for j in todo if job_key(j) in a.rows] or todo
    if a.rows:
        missing = set(a.rows) - {" > ".join(j["path"]) for j in todo} - {job_key(j) for j in todo}
        if missing:
            sys.exit(f"not provable rows in the scope: {sorted(missing)}")
    info_ok_jobs_or_exit(todo, proving.checklists.INFO_OK)
    if network:
        todo = network_jobs_or_exit(todo, network, proving.jobs.NETWORK_OPTIONS)
    cycle, model = load_scan(a.scan)
    CYCLE[:] = cycle
    MODEL.update(model)
    order = {}
    for i, p in enumerate(cycle):                       # rows in the menu's own Down order
        if p["kind"] == "menu" and p["page"] in model and p["row"] is not None and p["row"] < len(model[p["page"]]["rows"]) \
                and model[p["page"]]["rows"][p["row"]]["label"]:      # an OSD scan can leave a label unconfirmed
            order.setdefault(model[p["page"]]["rows"][p["row"]]["label"].lower(), i)
    todo.sort(key=lambda j: next((v for k, v in order.items() if same_text(k, j["path"][0])), 10 ** 6))
    run = Run(a.run)
    if network:
        run.make_private()          # owner-only from here (camkit.runs), checked at the end (seal)
        log_network_decided(run, network, proving.jobs.NETWORK_OPTIONS)
        KEPT.update(labels=known_labels(model) | set(network), values=known_values(model), by_row=row_values(model))
    done, failed, done_labels = {}, set(), {}
    help_text = proving.jobs.HELP_TEXT
    proofs, fails = ("option_help.jsonl", "help_failures.jsonl") if help_text else ("proofs.jsonl", "failures.jsonl")
    if help_text:
        if a.run == "kit2_pass2":
            sys.exit("--help-text writes no proofs: give it its own --run (kit2_help)")
        todo = [j for j in todo if j["kind"] in ("list", "dialog")]
    # the attempts prove_run finished: a cut-short attempt's proofs are left out of the report (pass2_report's
    # unfinished), so its options are made again rather than skipped (the Still Fn tile's two cut passes and a dial
    # cell stopped by the STOP file, 2026-11-07)
    complete = {x["attempt"] for x in jsonl.read(run.dir / "attempts.jsonl") if x.get("complete")}
    for r in jsonl.read(run.dir / proofs):     # resume: rows whose every option is proved (or read)
        if help_text and r.get("context") != a.context:
            continue
        if r.get("attempt") and r["attempt"] not in complete:
            continue
        done.setdefault(proof_key(r), set()).add(tuple(r["index"]) if isinstance(r["index"], list) else r["index"])
        if r.get("kind") == "table":
            done_labels.setdefault(proof_key(r), {})[r["index"]] = r["label"]
    if not a.retry_failed:
        failed = {proof_key(r) for r in jsonl.read(run.dir / fails)}
    for j in todo:
        if j["kind"] == "table":                    # resume a cell cut off part way (table_order),
            had = done_labels.get(job_key(j), {})   # by index and label: a new walk can reorder a list
            j["done"] = sorted(k for k, lab in had.items() if k < len(j["labels"]) and j["labels"][k] == lab)
    if a.redo and a.rows:
        for j in todo:
            j.pop("done", None)
            done.pop(job_key(j), None)
    if not a.rows:
        todo = [j for j in todo if not planned(j) <= set(j.get("done", done.get(job_key(j), set())))
                and job_key(j) not in failed]
    if a.limit:
        todo = todo[:a.limit]
    print(f"{len(todo)} rows to prove, {sum(len(planned(j)) for j in todo)} options", flush=True)
    if a.list:
        for j in todo:
            left = len(planned(j) - set(j.get("done", done.get(job_key(j), set()))))
            print(f"   {job_key(j):60s} {j['kind']:9s} {len(planned(j)):3d} options"
                  + (f", {left} still to prove" if left < len(planned(j)) else ""), flush=True)
        return
    # no reader listed: stop before the link opens, nothing pressed; with nothing to prove no reader is asked, so the
    # start file (--start) goes back all the same, as a put-back must never need a reader
    if todo:
        check_readers()
    hdmi = eyes_from_config(run)
    out = Tagged(open(run.dir / proofs, "a", encoding="utf-8", newline="\n"), a.context,  # noqa: SIM115 (closed in the finally below)
                 {"allowance": allowance} if allowance else None)
    failures = open(run.dir / fails, "a", encoding="utf-8", newline="\n")  # noqa: SIM115 (closed in the finally below)
    pending, start, in_a_row, unrestored = list(todo), None, 0, False
    try:
        with restoring("putting the start file back"):    # an upload that raises: exit EXIT_UNRESTORED
            put_back_ok = not a.start or put_start_back(run, hdmi, Path(a.start),
                                                        **({"withheld": True} if network else {}))
        if not put_back_ok:
            print("the start file did not take: stopping", flush=True)
            pending, unrestored = [], True
        while pending:
            ending = None
            with Link(run) as link:
                hdmi.attach(link)
                eyes = OsdEyes(link, run) if a.eyes == "osd-all" else hdmi
                if screen.read(eyes.grab(save=False)).kind in ("menu", "tiles"):
                    link.press("menu", cleanup=True)
                    time.sleep(1.0)
                to_shooting(link, eyes, "the settings download")
                here = link.download("before" if start is None else "session")
                if start is None:
                    start = here
                    print(f"start file: {start.name}", flush=True)
                    if camset.read(start).model != body:
                        print(f"the camera is a {camset.read(start).model}, the jobs were made for a {body}: stopping",
                              flush=True)
                        break
                elif camset.diff(camset.read(start), camset.read(here)):
                    print("a new session does not start from the start file's settings: stopping", flush=True)
                    unrestored = True
                    break
                time.sleep(5)
                left = len(pending)
                try:
                    status = session(link, eyes, run, cycle, model, pending, start, out, failures)
                except Exception as e:      # the session's own cancel at its end (a press the camera refused)
                    print(f"error closing the session: {type(e).__name__}: {e}; restoring", flush=True)
                    status = "error"
                print(f"{left - len(pending)} rows done this session", flush=True)
                unreached = []

                def reach(lk, ey, why, unreached=unreached):
                    try:
                        try:
                            to_shooting(lk, ey, why)
                        except RuntimeError as e:
                            # the HDMI feed did not come back after a row changed the signal: the OSD can still
                            # see the shooting screen, and the restore needs no eyes (2026-10-30)
                            print(f"   HDMI: {e}; looking through the OSD for the restore", flush=True)
                            to_shooting(lk, OsdEyes(lk, run), why)
                    except Exception:
                        unreached.append(why)
                        raise

                # the restore is tried even when the shooting screen does not come back (decision 15): a Failed
                # here once skipped finish and left the camera changed
                ending = end_rows(link, eyes, start, reach)     # keys alone on a --network run
                if unreached:
                    status = "error"                         # restored; no further session from an unknown screen
                if ending.after is None:
                    unrestored = True
                    break                                    # the camera kept refusing the download: finish said so
            if ending.uploaded and check_restore(run, ending, start, **values_withheld(bool(network))) != 0:
                print("the restore did not check out: stopping", flush=True)
                unrestored = True
                break
            proved_some = left - len(pending) > 1            # the failed row itself is popped too
            in_a_row = (1 if proved_some else in_a_row + 1) if status == "failed" else 0
            if status in ("done", "stop", "error") or not pending:
                break
            if in_a_row >= 3:
                print("three rows failed in a row: stopping", flush=True)
                break
        print(f"finished: {len(todo) - len(pending)} of {len(todo)} rows handled; "
              f"failures logged in {run.dir / fails}", flush=True)
    finally:
        if hdmi is not None:
            hdmi.close()
        out.close()
        failures.close()
        run.seal()                  # a --network run's folder checked owner-only
    if unrestored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


if __name__ == "__main__":
    main()
