"""Reset each Picture Profile with its own Reset on the camera, a download after each (2026-11-11).

    .venv/bin/python -u kit/provers/pp_reset_run.py --dry-run --allow "Picture Profile Reset" [--in Stills]
    .venv/bin/python -u kit/provers/pp_reset_run.py --peek --allow "Picture Profile Reset" [--in Stills]
    .venv/bin/python -u kit/provers/pp_reset_run.py --allow "Picture Profile Reset" [--in Stills|Movie]
                                                   [--profiles PP1,PP2] [--control-profile PP1] [--no-control]
                                                   [--need-both-readers | --ocr-alone-ok] [--scan RUN] [--run NAME]

Why: a definition's public sample (kit/tools/make_sample.py) is made from a download taken right after Initialize, and
Initialize on the a1 II leaves the Picture Profile parameters as they were, so the sample may hold the owner's own
profile edits (decision 16). The owner's word (2026-11-11): the kit resets each profile with the profile's own Reset on
the camera, downloads, the reset values go into the sample (make_sample.py --take ... --from <this run's result>), and
the owner's file is put back. A reset for a proof is allowed only the narrowest, with the owner's word, the owner's file
put back after (decision 5): the Reset row of one profile's own settings resets that profile and nothing else.

What the kit's records show of the row (runs/ILCE-1M2_fw4.00: the Stills crawl kit2_panels, the menu tree in
private/evidence): Picture Profile is a carousel (Off, the profiles); Right on a profile opens its settings panel,
which the reader takes for a submenu, titled with the profile's name ("PP1") and holding eleven rows, Black Level,
Gamma, Black Gamma, Knee, Color Mode, Saturation, Color Phase, Color Depth, Detail, Copy and Reset, Reset the last, Down
from it wrapping to Black Level (kit2_panels 02353_down.png, then 02354). The walk skipped Reset (never-open since
2026-10-28) and Copy: no run has opened either, so no frame of the question it asks exists, nor of which button it
lights first. --peek is that first look.

One session, bracketed as every prover's is (decision 15; runner.prover_session): the start file downloaded first
(the camera's own settings; the mode it was saved in, camera.live_mode, must be the one --in names, else the run stops
with nothing pressed), the menu as the page scan of the mode the camera is in has it (--in, --scan), then
  1. the profiles: MENU, the Picture Profile row by the scan, Right into its carousel, each option read on the way
     round (Down until the first comes back), MENU out with no choice: the profiles the camera's own list offers, PP and
     a number (a Movie mode's User1-User4, profiles that apply an imported LUT, are left alone). Every carousel label,
     panel title, question and notice this run judges is read by OCR and by the vision model, asked of every frame
     judged (the owner, 2026-11-11: so OCR's bad letters and Cyrillic look-alikes are caught), once per frame; the lit
     row it opens or moves (Reset, the control's Black Level) is read by OCR and must read as that row's name. A label is taken when both read the same name
     (label_kind: safety.fold and the digits' look-alikes, "PРЗ" is PP3); the vision model unreachable or reading
     nothing, OCR's reading as before; OCR's reading nothing, the vision model's; the two reading two names, looked at
     on two fresh frames more, then the run stops before any reset; neither reading: it stops, naming the label and
     its frame. A profile read twice stops the run; so does a list whose profiles are not the recorded walk's (the
     menu tree), unless --profiles names exactly the profiles to reset. --profiles keeps some (such a run can never
     feed the sample: make_sample.py needs every offered profile reset); one the list does not offer stops the run
     before any reset. The carousel is found the same way in step 2 (to_profile, not prove_run's enter_pp). The
     carousel's labels guard no press (the panel's title and the question do, below), so a label read by one reader
     alone is taken and said ("labels_single_reader").
  1b. the positive control (not in a peek; --no-control only for a peek or a --profiles trial, and such a result never
     feeds the sample): "no record changed" after the resets would say nothing if a Reset wrote none of the records a
     settings file saves. So, before the resets, ONE profile (the first offered, or --control-profile, which is then
     reset first) has ONE parameter moved by one step on the camera, as prove_run --pp moves a Picture Profile side
     list (proving.sidelists): MENU, the row by the scan, the carousel to the profile, Right into its settings
     (confirmed as the profile's: back_on_panel), Down to Black Level (find_row; CONTROL_ROW: the panel's first row, a
     side list of numbers, an image parameter like every Picture Profile parameter; a row find_row reached by its
     closest reading whose own name does not read as Black Level is never moved), Right opens its side list, the
     number under the cursor read (OCR and the vision model: list_value), Down or Up once, away from 0 (at an end of
     the scale, where the list wraps, back and one step the other way), the new number read and checked to be one step
     from the old, Enter (chosen), the panel checked back as the profile's by its title (back_on_panel). Every press
     goes through the kit's ordinary guarded press path; no allowance is used. A STOP file is looked for before and
     after it. MENU out and a download (control-set): at least one of the profiles' parameters must differ from the
     start file, their keys kept ("control.changed", ids only, and how many are the in-use record, the "(stills)" copy
     and the "(movie)" copy: "copies_changed"), and, element by element by the definition's layout
     (make_sample.control_change_of), each changed record may differ only in that profile's element, and the record in
     use and the copy of the run's mode must be among them. After that profile's Reset (the first reset) that
     profile's element of every record the control changed must differ between control-set and the reset's download
     ("reset_wrote", "copies_reset_wrote", "ok"; another profile's element moving does not count). Any check failing:
     "ok" false, the run stops there (the start file goes back as always) and exits non-zero.
  2. per profile, a STOP file (runs/<model>_fw<fw>/<run>/STOP) looked for first, never with a dialog open: MENU, the
     row by the scan, Right, the carousel to the profile, Right into its settings (what entering alone does to the
     records, the profile in use among them, is not assumed: the verify pass, step 3, looks);
     Down to Reset (find_row). The lit row must read Reset alone and the panel's title be the
     profile's (safety.profile_reset_row) on the frame the press is judged on: OCR's title as read (profile_title), or
     OCR's naming the profile once the digits' look-alikes are read as digits AND the vision model reading the
     profile's name alone (profile_title_agreed: two readers agreeing); a vision or OCR title naming any other profile
     anywhere in its text refuses ("Picture Profile PP10" for PP1). With --need-both-readers (on by default for a run
     that is not a peek and not limited by --profiles; --ocr-alone-ok turns it off) the vision model must also have
     read the title as naming this profile, and the question below as naming it: a reading it could not give (not
     reachable, nothing parseable) refuses that press and stops the run before it. Without it such a press goes on
     OCR's reading alone, and each profile keeps which way its title and its question were judged ("readers":
     {"title", "question"}: "both" or "ocr").
     While it refuses, up to three fresh frames are judged, no press between (row_judged), and the way that accepted is
     logged. Only then is that one row lifted for that one press (LiveCamera.may_open_exact: the camera judges the
     press on the same frame, the lit row Reset alone, the title passing the same check; "Reset" is never added to
     may_open). The question must be the profile's own (safety.profile_reset_dialog: the kit's confirmation check takes
     it for one, it reads reset, the profile's name and default, "Reset PP1 to the default setting?" on the a1 II,
     names no other profile and nothing another reset or no allowance holds), and the vision model's reading of it,
     logged, must name no other profile. OK is lit when it opens (the peeks); if not, only Up and Down, at most two
     moves, the question read on a fresh frame before and after each and judged whole again; Enter goes only on a lit
     OK on the frame on screen, judged by drive.py's own Enter guard too. Anything else: MENU (cancel, never OK) and
     the run stops, nothing reset. After OK the camera's completion notice is expected (after_ok): "Complete." over
     one lit OK on the a1 II (kit2_pp_reset_trial 00043_enter.png), its whole text that and nothing else in every
     OCR reading and in the vision model's when it answers (safety.profile_reset_complete). It is kept ("complete":
     true, its frame) and closed as the kit closes a notice that asks nothing: MENU (which the a1 II took on it back to
     the profile's settings), OK only if MENU is refused, through drive.py's Enter guard. The profile's settings
     straight after OK, confirmed, are taken too and recorded so ("complete": false: another body may show no notice;
     make_sample.py refuses such a result unless --allow-no-notice). Anything else
     after OK (another notice, a question, "This function is currently disabled", a panel of another title), looked at
     on two frames: MENU only, its words logged, and the run stops, the profile not counted. After the notice the
     profile's settings are looked for (back_on_panel: a submenu titled with its name, by OCR as read, by OCR with the
     look-alikes and the vision model agreeing or unable to say, or by the vision model for a title OCR reads as no
     name; never one either reader reads as another profile). This guards no press, and the camera has said Complete,
     so a screen it cannot confirm then does not stop the run: what was read is said and kept ("back": "unconfirmed",
     its words in events.jsonl), and the profile counts as reset. A profile counts as reset when OK went on the
     accepted question and the completion notice was seen or its settings came straight back. MENU out, a download
     named for the profile (reset-PP1, ...).
  3. the verify pass: "changed between two downloads" is not "written by the reset" unless entering a profile's
     settings alone changes nothing. Every profile reset is entered once more, the panel confirmed as the profile's by
     its title as after a Reset (back_on_panel; under --need-both-readers the vision model's reading must name the
     profile too), and left with MENU, no Reset opened, then a download (verify); the profiles' parameters that differ
     between the last reset's download and it are kept (ids only), and each entry's confirmation ("verify"."entered":
     {profile: "confirmed" or "unconfirmed"}). Any parameter moved, or any entry unconfirmed: "verified": false, the
     exit non-zero, and make_sample.py refuses the result. The run counts as finished only after this pass.
  4. the session's end: the camera closed back to the shooting screen, the start file uploaded and the restore
     checked (0 records differ), which also puts back the profile in use. The console and the restore name no value
     (show=0); every exit path (an error, a STOP, a refusal, one Ctrl-C) ends there, as every prover's does.
The result, pp_reset.json in the run folder, is written after each profile: "mode" (as --in told it) and "start_mode"
(as the start file says), "family", "asked" (--profiles, or null), "offered" (the labels) and "offered_profiles"; per
profile its frames, the question as read (and as the vision model read it), "readers", its download, and the record
keys that changed between the download before it (control-set for the first, or the start file when there is no
control) and its own ("changed", and of them the profiles' parameters, "family_changed"; ids only); "control" (above;
null with --no-control, "control_skipped" saying why); "need_both_readers"; "labels_single_reader"; "last", the last
reset's download, relative to the run folder; "verify" and "verified"; "finished", false (and the exit non-zero) when
the run stopped, or when, without --profiles, fewer profiles were reset than the camera offered;
"completion_notice", how many profiles showed the camera's completion notice, and "no_notice", how many came straight
back with none (each profile's "complete" and "complete_frame" say which); "back_unconfirmed", the profiles not seen
back on their settings after the completion notice (the run still finishes); the console's last line says the counts
and names those. kit/tools/make_sample.py --from takes it, and checks every list in it against the run's own
downloads. Nothing is a proof line: the run proves no setting's values, it makes the files the sample is taken from.

Whether a profile's Reset in Stills mode also resets the Movie copy of its parameters (each parameter is kept three
times: in use, stills, movie) is not known: run it in Stills, then in Movie (kit/provers/mode_switch.py --to Movie
--keep, this run --in Movie, mode_switch.py --restore), each run in its own folder (kit2_pp_reset_stills,
kit2_pp_reset_movie); make_sample.py takes the in-use and stills copies from the Stills run and the movie copies from
the Movie run.
--peek opens the first profile's Reset, records what the question shows (its frame, kind, text, lit button, and whether
the guards accept it), cancels with MENU, checks the profile's settings came back, and downloads, so the keys changed
since the start say whether opening alone reset anything (pp_reset_peek.json); it resets nothing.
--dry-run prints the plan from the page scan and the recorded walk (the control's profile and parameter among it),
with no link. A camera run, a peek and a dry run
all need the owner's word, --allow "Picture Profile Reset", and no other --allow (safety.PROFILE_RESET).
No key on the shooting screen but MENU (decision 21); nothing that makes sound, light or motion is touched.
"""
import argparse
import contextlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(1, str(Path(__file__).resolve().parent))
sys.path.insert(2, str(Path(__file__).resolve().parents[1] / "tools"))
from camkit import camset, definitions, match, paths, safety  # noqa: E402
from runner import (LATEST_SCAN, add_allow_argument, add_in_argument, allowed_or_exit, in_mode,  # noqa: E402
                    scan_arg, scan_dir, write_json)

ROW = "Picture Profile"
RESET_ROW = "Reset"
ALLOW = safety.PROFILE_RESET
MODES = ("Stills", "Movie")
RESULT, PEEK_RESULT = "pp_reset.json", "pp_reset_peek.json"
FAMILY = "Picture Profile PP"            # the definition's family of the profiles' parameters (camera.families)
TITLE_BOX = (0, 0, 640, 52)              # a panel's title line, as mode_switch.set_row reads it
OK_BUTTON = re.compile(r"\W*(?:ok|enter)\W*", re.I)
CANCEL_BUTTON = re.compile(r"\W*cancel\W*", re.I)
MOVES = ("up", "down")                   # at most these two, from a lit Cancel, the question judged again after each
AGREE_FRESH = 2                          # fresh frames a carousel option is read on while OCR and the vision model differ
OPEN_KEYS = ("right", "enter")
LAP = 30                                 # at most this many options read on the carousel's way round
NOT_A_DIALOG = frozenset({"shooting", "menu", "submenu", "tiles"})
ROW_FRESH = 3                            # fresh frames the guard before Reset looks at while it refuses (row_judged)
AFTER_OK_LOOKS = 2                       # frames the screen after OK is judged on before it counts as unknown (after_ok)
# The positive control's parameter: Black Level, the first row of a profile's settings (find_row reaches it at once,
# as prove_run --pp's Black Level proofs did, Right on the panel opening its side list) and a side list of numbers
# one step apart (proving.sidelists: Down one way, Up the other, the lap wrapping at the scale's ends), the kind of
# list prove_run --pp drives most simply. Every Picture Profile parameter is an image parameter: nothing it can be set
# to makes sound, light or motion
CONTROL_ROW = "Black Level"
CONTROL_TAG = "control-set"
CONTROL_FRESH = 2                        # fresh frames a side list's number is read on while the two readers differ


def default_run(mode: str) -> str:
    return f"kit2_pp_reset_{mode.lower()}"


# ---------------------------------------------------------------- the plan (no camera)

# The digits' look-alikes, a carousel label's kinds and a title's name live in camkit.safety (profile_label_kind,
# profile_title_names): the guard before Reset takes a look-alike title only with the vision model's agreeing
# (safety.profile_title_agreed), so the rule is beside the strict one it adds to.
DIGIT_LOOKALIKES = safety.PROFILE_DIGIT_LOOKALIKES
OPTION_NAME = safety.PROFILE_OPTION
label_kind = safety.profile_label_kind
title_names = safety.profile_title_names


def profile_of(label) -> str | None:
    """The profile an option's label names ("PP3"; OCR's "PP 3" and "PРЗ" too), or None (Off, a LUT profile, a label
    no rule reads: label_kind tells these apart)."""
    kind, name = label_kind(label)
    return name if kind == "profile" else None


def profiles_of(labels) -> list:
    """The profiles a list of option labels names, each once, in their number's order."""
    got = {p for p in (profile_of(x) for x in labels or []) if p}
    return sorted(got, key=lambda p: int(p[2:]))


def asked_profiles(given) -> list:
    """--profiles (comma-separated, repeatable) as profile names; exits on one that is not PP and a number."""
    out = []
    for item in given or []:
        for part in str(item).split(","):
            if not part.strip():
                continue
            p = profile_of(part)
            if p is None or not safety.PROFILE_NAME.fullmatch(part.strip().upper().replace(" ", "")):
                sys.exit(f"pp_reset_run: --profiles {part.strip()!r} is not a Picture Profile's name (PP and its "
                         "number, as the camera writes it: PP1, PP10)")
            out.append(p)
    return list(dict.fromkeys(out))


def menu_tree_options(tree: dict, mode: str) -> list | None:
    """The options the camera's menu tree (kit/tools/menu_tree.py) records for the Picture Profile row in `mode`'s
    menu (Stills: the tree's own tabs; another mode: its entry in "modes"), or None when it records none: make_sample's
    own reading, which checks a result's offered profiles against it."""
    import make_sample
    return make_sample.menu_tree_options(tree, mode, ROW)


def recorded_profiles(camera: str, mode: str) -> tuple:
    """(the profiles the recorded walk lists, where it is) for the plan; (None, why) when no walk is recorded."""
    try:
        f = definitions.menu_tree_file(camera)
    except Exception as e:                  # the plan only: the run reads the camera's own list
        return None, f"no menu tree ({type(e).__name__}: {e})"
    if not Path(f).exists():
        return None, f"no menu tree at {paths.shown(Path(f))}"
    opts = menu_tree_options(json.loads(Path(f).read_text(encoding="utf-8")), mode)
    if opts is None:
        return None, f"{paths.shown(Path(f))} records no Picture Profile options in {mode} mode"
    return profiles_of(opts), paths.shown(Path(f))


def scan_row(scan: Path) -> dict | None:
    """Where the page scan's model (model.json) has the Picture Profile row: {"page", "slot"}, or None."""
    f = Path(scan) / "model.json"
    if not f.exists():
        return None
    for page in json.loads(f.read_text(encoding="utf-8")):
        for r in page.get("rows") or []:
            if isinstance(r, dict) and match.key(str(r.get("label") or "")) == match.key(ROW):
                return {"page": page.get("page"), "slot": r.get("slot")}
    return None


def family_ids(camera: str) -> set:
    """The record ids of the profiles' parameters (FAMILY, by the camera's public definition; make_sample's family
    lookup): for saying which changed keys are theirs. Empty when the definition or the family is not there."""
    import make_sample
    f = definitions.DIR / f"{camera}.json"
    if not f.exists():
        return set()
    return set(make_sample.family_ids(json.loads(f.read_text(encoding="utf-8")), FAMILY) or ())


def family_layout_of(camera: str) -> dict | None:
    """The profiles' parameters' layout by the camera's public definition (make_sample.family_layout: each record's
    copy and each profile's element), or None when the definition or the family is not there or does not tell its
    copies and elements apart."""
    import make_sample
    f = definitions.DIR / f"{camera}.json"
    if not f.exists():
        return None
    try:
        return make_sample.family_layout(json.loads(f.read_text(encoding="utf-8")), FAMILY)
    except SystemExit:
        return None


def family_copies(camera: str) -> dict | None:
    """{record id: "live" | "stills" | "movie"} for the profiles' parameters (family_layout_of), or None."""
    lay = family_layout_of(camera)
    return None if lay is None else {rid: r["copy"] for rid, r in lay["records"].items()}


def control_elements(camera: str, start: Path, control: Path, profile: str, mode: str) -> dict:
    """What the control's change did, element by element (make_sample.control_change_of over the start file and
    control-set, by the definition's layout): {"changed", "others", "missing"}; with no layout, every changed key
    counts as not shown ("others")."""
    import make_sample
    lay = family_layout_of(camera)
    if lay is None:
        return {"changed": [], "others": [], "missing": ["in-use", mode.lower()]}
    return make_sample.control_change_of(camset.read(start), camset.read(control), lay, profile, mode)


def control_wrote(camera: str, control: Path, reset: Path, profile: str, changed: list) -> list:
    """Those of the control's changed records whose `profile` element its Reset wrote (make_sample.control_wrote:
    that element differs between control-set and the reset's download; another profile's element moving does not
    count)."""
    import make_sample
    lay = family_layout_of(camera)
    if lay is None:
        return []
    return make_sample.control_wrote(camset.read(control), camset.read(reset), lay, profile, changed)


def copies(keys, cmap) -> dict | None:
    """How many of `keys` are the in-use record, the "(stills)" copy and the "(movie)" copy (make_sample.copies_of)."""
    import make_sample
    return make_sample.copies_of(keys, cmap)


def plan_lines(camera: str, mode: str, scan: Path, place: dict | None, recorded, where: str, asked: list,
               run_dir: Path, peek: bool, control: str | None = None, need_both: bool = False) -> list:
    """The plan in words: no value, only names, places and steps."""
    at = (f"page {place['page']}, row {int(place['slot']) + 1}" if place and isinstance(place.get("slot"), int)
          else "not in its page model: the run stops before any press")
    lines = [f"{camera}, {mode} mode: page scan {scan.name} (Picture Profile: {at})"]
    if recorded is None:
        lines.append(f"profiles: none recorded ({where}); the run reads the camera's own list")
    else:
        lines.append(f"profiles the recorded walk lists: {', '.join(recorded) or 'none'} ({where}); the run reads the "
                     "camera's own list again and resets the ones it offers; if its profiles are not these, it stops "
                     "before any reset unless --profiles names them")
    if asked:
        lines.append(f"--profiles: {', '.join(asked)} only" + (
            f" ({', '.join(p for p in asked if recorded is not None and p not in recorded)} not in the recorded walk)"
            if recorded is not None and any(p not in recorded for p in asked) else ""))
    todo = [p for p in (recorded or []) if not asked or p in asked] or asked
    if peek:
        lines.append(f"--peek: {todo[0] if todo else 'the first profile'}'s Reset opened, its question recorded, "
                     "cancelled with MENU; nothing reset")
    elif control:
        lines.append(
            f"positive control first: {control}'s {CONTROL_ROW} (an image parameter, a side list of numbers) moved one "
            f"step: MENU, Picture Profile by the scan, the carousel to {control}, Right into its settings, Down to "
            f"{CONTROL_ROW}, Right (its side list), Down or Up once away from 0, Enter; MENU out, download "
            f"{CONTROL_TAG}; at least one of the profiles' parameters must change, and after {control}'s Reset (the "
            "first reset) every record the control changed must differ from control-set, else the run stops")
    else:
        lines.append("no positive control (--no-control): this result can never feed the sample")
    lines += [
        "every name (carousel labels, the panel's title, the question) read by OCR and the vision model, once a frame; "
        "two different names stop the run; a title or question naming another profile anywhere refuses",
        ("both readers needed (--need-both-readers): Reset is not opened, nor OK pressed, on OCR's reading alone"
         if need_both else "OCR alone may judge the title and the question when the vision model gives no reading "
         "(each profile's readers are kept; make_sample refuses such a result)"),
        "per profile: MENU, Picture Profile by the scan, Right, the carousel to the profile, Right into its settings, "
        "Down to Reset; Reset opened only when it reads Reset alone under the profile's own title (as read, or OCR "
        "with look-alikes and the vision model agreeing), lifted for that one press on that frame",
        "  the question must read 'Reset <profile> to the default setting?' (safety.profile_reset_dialog), the vision "
        "model naming no other profile, OK lit (else Up, Down at most), else MENU and stop; OK, then the camera's "
        "'Complete.' notice (both readers) closed with MENU, or the profile's settings straight back; any other screen: "
        "MENU and stop; after the notice the profile's settings looked for (not seen: kept as unconfirmed, not a "
        "stop), MENU out, download reset-<profile>; settings straight back with no notice: complete false, which "
        "make_sample refuses unless --allow-no-notice",
        "then the verify pass: every profile reset entered again, its panel confirmed by its title, and left with "
        "MENU, a download (verify); any of the profiles' parameters changed by it, or a panel not confirmed: not "
        "verified, exit non-zero, make_sample refuses the result",
        f"a STOP file ({paths.shown(run_dir / 'STOP')}) stops the run between profiles; every exit uploads the start "
        "file and checks it (0 records differ)",
        f"result: {paths.shown(run_dir / (PEEK_RESULT if peek else RESULT))}"]
    return lines


def allowance_of(allow) -> str:
    """The owner's word: --allow names PROFILE_RESET and nothing else, else the run stops before anything (a dry run
    too); runner.allowed_or_exit then says it and gives its words."""
    if not safety.named(ALLOW, allow):
        sys.exit(f"pp_reset_run: a Picture Profile's Reset is a reset, on the never-open list; this run opens it only "
                 f"with the owner's word for it, --allow {ALLOW!r}. Nothing was sent to the camera.")
    others = [x for x in allow if not safety.named(ALLOW, [x])]
    if others:
        sys.exit(f"pp_reset_run: --allow names {others}: this run opens no never-open row but a Picture Profile's own "
                 f"Reset ({ALLOW!r}). Nothing was sent to the camera.")
    return allowed_or_exit(allow)


# ---------------------------------------------------------------- the camera

def title(cam) -> str:
    """The text of the screen's title line, as OCR reads it."""
    from camkit import ocr
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], TITLE_BOX).strip()


# ---------------------------------------------------------------- the vision model, asked of every name

def ask_reader(path, prompt: str) -> dict | None:
    """The kit's second reader's answer about the frame at `path` (camkit.vlm.PROMPTS[prompt], through
    proving.screens.ask_second, a stand-in taking the role when the second will not connect), or None when no reader
    answered with an object (unreachable, failed, or an answer of another shape)."""
    from camkit.vlm import PROMPTS
    from proving.screens import ask_second
    try:
        v = ask_second(Path(path).read_bytes(), PROMPTS[prompt], timeout=25)
    except Exception:
        return None
    return v if isinstance(v, dict) else None


def second_answer(cam, prompt: str = "option") -> dict | None:
    """The vision model's answer about the frame on screen, asked once per frame and prompt (kept on the camera
    object, so a frame judged twice costs one call) and logged (pp_reset_second): None when it is not reachable. The
    owner (2026-11-11): every label, title, question and notice this run judges is read by the vision model as a
    matter of course, not only when OCR fails, so OCR's bad letters and Cyrillic look-alikes are caught by a second
    reading."""
    cache = getattr(cam, "_pp_second", None)
    if cache is None:
        cache = {}
        cam._pp_second = cache
    k = (str(cam.frame.path), prompt)
    if k not in cache:
        cache[k] = ask_reader(cam.frame.path, prompt)
        cam.run.log("pp_reset_second", frame=cam.frame.path.name, prompt=prompt, answer=cache[k],
                    reachable=cache[k] is not None)
    return cache[k]


def second_field(cam, field: str, prompt: str = "option") -> str | None:
    """One field of the vision model's answer (second_answer) as text: None when the reader is not reachable, "" when
    it gave none."""
    v = second_answer(cam, prompt)
    return None if v is None else str(v.get(field) or "").strip()


def second_title(cam) -> str | None:
    """The vision model's reading of the screen's title (PROMPTS["option"]'s "title"), None when not reachable."""
    return second_field(cam, "title")


def second_option(cam) -> str | None:
    """The vision model's reading of the item under the cursor (PROMPTS["option"]'s "selected", as
    prove_run.vlm_option asks it), None when not reachable."""
    return second_field(cam, "selected")


def question_names(answer) -> list:
    """The profiles (PP and a number) any text of the vision model's answer about a question names, each once, the
    digits' look-alikes read as digits (safety.profile_names_in: "PР1O" is PP10)."""
    texts = []

    def walk(x):
        if isinstance(x, str):
            texts.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(answer)
    return list(dict.fromkeys(n for t in texts for n in safety.profile_names_in(t)))


def title_readers(second, profile: str) -> str:
    """How the panel's title before Reset was judged: "both" when the vision model's reading names `profile` and no
    other (safety.profile_names_in), else "ocr" (not reachable, nothing read, or a reading naming no profile)."""
    return "both" if second is not None and safety.profile_names_in(second) == [profile] else "ocr"


def question_readers(answer, profile: str) -> str:
    """How the question was judged: "both" when the vision model's answer about it names `profile` and no other
    (question_names), else "ocr" (not reachable, an answer of another shape, or naming no profile)."""
    return "both" if answer is not None and question_names(answer) == [profile] else "ocr"


NEED_BOTH = ("--need-both-readers refuses a press judged on OCR's reading alone (--ocr-alone-ok allows it, for a "
             "trial whose result never feeds the sample)")


@contextlib.contextmanager
def reset_lifted(cam, exact):
    """The one Reset row lifted from LiveCamera's never-open check for the one press inside: `exact`, a predicate
    (frame, lit) the camera applies to the frame it judges that press on (LiveCamera.may_open_exact, used up by the
    press), never a name added to may_open (which LiveCamera compares as a part of a row's text: any row holding
    "reset" would open). Put back (None) after whatever happens; the run's may_open names are not touched."""
    cam.may_open_exact = exact
    try:
        yield
    finally:
        cam.may_open_exact = None


def back_out(cam, why: str):
    """MENU on a screen opened over the panel (a dialog: MENU cancels it, never OK), then the run stops."""
    from prove_run import Failed
    if cam.read().kind not in NOT_A_DIALOG:
        cam.press("menu")
    raise Failed(f"{why} ({cam.frame.path.name}): backed out with MENU, nothing reset")


def option_here(cam) -> tuple:
    """(the label as OCR read it, the label taken, kind, name, by) for the carousel option under the cursor. The
    vision model is asked of every option (second_option); OCR's reading and the vision model's are each judged by
    label_kind (fold and the digits' look-alikes). by: "both" when they agree on the same name; "ocr" when the vision
    model is not reachable or read nothing a rule reads (OCR's reading judged as before); "second" when OCR's reads as
    nothing and the vision model's does (as before: the second reader for a label OCR does not read); "disagree"
    (kind "disagree", name None) when they read two different names, which the caller looks at again on fresh frames
    and otherwise stops on; "none" (kind "unread") when neither reads."""
    from prove_run import carousel_text
    t = carousel_text(cam)
    kind, name = label_kind(t)
    v = second_option(cam)
    vkind, vname = label_kind(v) if v else ("unread", None)
    if vkind == "unread":
        out = (t, t, kind, name, "ocr" if kind != "unread" else "none")
    elif kind == "unread":
        out = (t, v, vkind, vname, "second")
    elif (kind, name) == (vkind, vname):
        out = (t, t, kind, name, "both")
    else:
        out = (t, v, "disagree", None, "disagree")
    cam.run.log("pp_reset_option", frame=cam.frame.path.name, ocr=t, second=v, reads_as=out[2], name=out[3], by=out[4])
    return out


def option_read(cam, fresh: int = AGREE_FRESH) -> tuple:
    """option_here, and while the two readers read different names, up to `fresh` fresh frames more (no press
    between); still apart: Failed, naming both readings and the frame, before any reset."""
    from prove_run import Failed
    for look in range(fresh + 1):
        got = option_here(cam)
        if got[2] != "disagree":
            return got
        if look < fresh:
            time.sleep(0.4)
            cam.refresh("reread")
    raise Failed(f"the {ROW} option on {cam.frame.path.name} reads {got[0]!r} to OCR and {got[1]!r} to the vision "
                 f"model, two different names on {fresh + 1} frames: the run stops before any reset rather than guess")


def read_profiles(cam, link, cycle, model, say, kept: dict | None = None) -> list:
    """Step 1: the carousel's options read on the way round (Down until the first comes back), MENU out with no
    choice, back to the shooting screen. Returns the labels in the carousel's order: OCR's reading where the vision
    model agrees or cannot say, the vision model's for one OCR's does not give (option_here). A label neither reading
    gives, or that the two read as two names, stops the run here, before any reset, naming it and its frame: never
    skipped. `kept`, when given, gets "single": the names read by one reader alone (no press acts on a label: the
    panel's title and the question are the guards)."""
    from mode_switch import find, open_menu
    from prove_run import Failed
    from runner import close_screen
    open_menu(cam)
    find(cam, cycle, model, ROW)
    cam.press("right")
    if cam.read().kind != "dialog":
        raise Failed(f"Right on {ROW} opened {cam.read().kind}, not its carousel ({cam.frame.path.name})")
    seen, names, ways = [], [], []
    for _ in range(LAP):
        time.sleep(0.4)
        cam.refresh("reread")
        read, taken, kind, name, by = option_read(cam)
        if kind == "unread":
            raise Failed(f"an option of the camera's {ROW} list reads {read!r} ({cam.frame.path.name}), which is "
                         "neither Off, a profile (PP and a number) nor User1-User4, and the second reader could not "
                         "read it either: the run stops before any reset rather than skip it. Look at that frame; if "
                         "it is a profile, run again (the reading may come right) or name the profiles with --profiles")
        if taken != read:
            say(f"   the option on {cam.frame.path.name} reads {read!r}: the second reader reads {taken!r} ({name})")
        if len(names) > 1 and name == names[0]:
            break
        if not names or name != names[-1]:   # the same name again: Down not taken yet
            seen.append(taken)
            names.append(name)
            ways.append(by)
        cam.press("down")
    else:
        raise Failed(f"the {ROW} carousel did not come round in {LAP} options ({cam.frame.path.name})")
    cam.press("menu")                        # out of the carousel with no choice
    close_screen(cam, link)
    alone = [n for n, w in zip(names, ways, strict=True) if w != "both"]
    if kept is not None:
        kept["single"] = alone
    say(f"the camera's {ROW} list: {', '.join(seen)}" + (
        f" (read as {', '.join(names)})" if [match.key(x) for x in seen] != [match.key(x) for x in names] else "")
        + (f"; read by one reader only: {', '.join(alone)}" if alone else "; every name read alike by OCR and the "
           "vision model"))
    return seen


def to_profile(cam, profile: str):
    """From the Picture Profile row: Right into the carousel, Down until the option under the cursor is `profile`
    (option_read: OCR and the vision model, look-alikes read as their letters and digits; two readers reading two names
    stop the run), Right into its settings. As
    proving.nav.enter_pp, which compares readings without the digits' look-alikes and so never found PP3 read as "PРЗ".
    The panel's guards (safety.profile_reset_row, on its title) are the same either way."""
    from prove_run import Failed, at_label
    if cam.read().kind != "menu" or not at_label(cam, "menu", ROW):
        raise Failed(f"not on the {ROW} row ({cam.read().kind}, {cam.frame.path.name})")
    cam.press("right")
    if cam.read().kind != "dialog":
        raise Failed(f"Right on {ROW} opened {cam.read().kind}, not its carousel ({cam.frame.path.name})")
    for _ in range(LAP):
        time.sleep(0.4)
        cam.refresh("reread")
        if option_read(cam)[3] == profile:
            break
        cam.press("down")
    else:
        raise Failed(f"the {ROW} carousel never showed {profile} in {LAP} options ({cam.frame.path.name})")
    cam.press("right")
    if cam.read().kind != "submenu":
        raise Failed(f"Right on {profile} opened {cam.read().kind}, not its settings ({cam.frame.path.name})")


def control_back_out(cam, why: str):
    """MENU on a side list or a notice the control opened (MENU closes a side list with no choice), then the run
    stops: the start file goes back as always."""
    from prove_run import Failed
    if cam.read().kind not in NOT_A_DIALOG:
        cam.press("menu")
    raise Failed(f"control: {why} ({cam.frame.path.name}): backed out with MENU; the run stops before any reset")


def list_value(cam, fresh: int = CONTROL_FRESH) -> float | None:
    """The number under a side list's cursor (proving.sidelists.signed): OCR's (side_text, else the cursor bar alone
    enlarged, bar_ocr) and the vision model's (vlm_option), taken where both read the same number, or where one reads
    a number and the other none; two numbers apart, up to `fresh` fresh frames more, then None. No value is logged or
    said (whether each reader read a number and whether they agreed is). Not a guard: every value of the control's
    row is harmless; it says only which way is one step."""
    from proving.screens import vlm_option
    from proving.sidelists import bar_ocr, side_text, signed
    for look in range(fresh + 1):
        s = cam.read()
        if s.kind != "sidelist":
            return None
        o = signed(side_text(cam))
        if o is None and getattr(s, "bar", None):
            o = signed(bar_ocr(cam))
        v = signed(vlm_option(cam))
        got = o if v is None else v if o is None else o if o == v else None
        cam.run.log("pp_reset_control_value", frame=cam.frame.path.name, look=look + 1, ocr_read=o is not None,
                    second_read=v is not None, agree=None if o is None or v is None else o == v,
                    taken=got is not None)
        if got is not None:
            return got
        if look < fresh:
            time.sleep(0.4)
            cam.refresh("control-value")
    return None


def row_reads_as(cam, label: str) -> str | None:
    """None when the lit row's own reading is `label` (proving.screens: the same text, its short first word kept),
    else what it reads: find_row may land on the closest reading of a panel's rows and remember it (screens.SEEN), so
    at_label alone would pass a row whose name is not the parameter's."""
    from proving.screens import bar_text, glued, keeps_lead, same_text
    t = bar_text(cam)
    return None if same_text(t, glued(label)) and keeps_lead(t, label) else t


def one_step(a, b) -> bool:
    return a is not None and b is not None and abs(abs(b - a) - 1) < 1e-6


def control_change(cam, cycle, model, profile: str, say) -> dict:
    """Step 1b's presses: `profile`'s CONTROL_ROW moved by one step, as prove_run --pp moves a side list
    (proving.sidelists.prove_side_row): MENU, the row by the scan, the carousel to the profile, Right into its
    settings (back_on_panel must confirm the title is the profile's), Down to the row (find_row, then the lit row
    read as it), Right (its side list), the number read (list_value), Down when it is 0 or less, Up when more (away
    from 0, where a profile's reset value of an image parameter may well lie: a step onto the reset value would make
    the check after the Reset fail, never pass), the number read again and checked one step from the first; when it
    is not (the scale's end, where the lap wraps), the other key twice, back and one step the other way, checked the
    same; Enter (the value chosen), the panel checked back as the profile's (back_on_panel: its title, not only the
    kind of screen). A row find_row reached by its closest reading, whose own name does not read as the parameter
    (row_reads_as), is never moved. Every press goes through the camera's ordinary guards.
    Anything else: MENU and the run stops. Returns the frames and the keys pressed in the side list (no value)."""
    from mode_switch import find, open_menu
    from prove_run import Failed, at_label
    from proving.nav import find_row
    open_menu(cam)
    find(cam, cycle, model, ROW)
    to_profile(cam, profile)
    back = back_on_panel(cam, profile)
    if back["back"] != "confirmed":
        raise Failed(f"control: Right on {profile} opened a panel not read as {profile}'s ({looks_said(back)}): "
                     "nothing changed; the run stops before any reset")
    if not find_row(cam, CONTROL_ROW) or not at_label(cam, "submenu", CONTROL_ROW):
        raise Failed(f"control: no {CONTROL_ROW} row lit in {profile}'s settings ({cam.frame.path.name}): nothing "
                     "changed; the run stops before any reset")
    lit = row_reads_as(cam, CONTROL_ROW)
    if lit is not None:                      # find_row's closest reading, not the row's own name
        raise Failed(f"control: the lit row in {profile}'s settings reads {lit!r}, not {CONTROL_ROW} "
                     f"({cam.frame.path.name}; the closest reading of the panel's rows): the control moves only the "
                     "row whose name reads as the parameter it names; nothing changed, the run stops before any reset")
    row_frame = cam.frame.path.name
    cam.press("right")
    if cam.read().kind != "sidelist":
        control_back_out(cam, f"Right on {CONTROL_ROW} opened {cam.read().kind}, not its side list")
    list_frame = cam.frame.path.name
    v = list_value(cam)
    if v is None:
        control_back_out(cam, f"the number under {CONTROL_ROW}'s cursor could not be read")
    first = "down" if v <= 0 else "up"
    other = "up" if first == "down" else "down"
    moves = []

    def move(key):
        cam.press(key)
        moves.append(key)
        if cam.read().kind != "sidelist":
            control_back_out(cam, f"{key.capitalize()} in {CONTROL_ROW}'s side list left it ({cam.read().kind})")
    move(first)
    w = list_value(cam)
    if not one_step(v, w):
        move(other)
        move(other)
        w = list_value(cam)
        if not one_step(v, w):
            control_back_out(cam, f"{CONTROL_ROW}'s side list did not show a number one step from the first after "
                                  f"{', '.join(moves)}")
    chosen = cam.frame.path.name
    cam.press("enter")
    if cam.read().kind != "submenu":
        control_back_out(cam, f"after Enter on {CONTROL_ROW}'s side list the screen reads as {cam.read().kind}, not "
                              f"{profile}'s settings (a notice: the value refused)")
    back = back_on_panel(cam, profile)
    if back["back"] != "confirmed":
        raise Failed(f"control: after Enter on {CONTROL_ROW}'s side list the panel is not read as {profile}'s "
                     f"({looks_said(back)}); the run stops before any reset (the start file goes back)")
    say(f"control: {profile}'s {CONTROL_ROW} moved one step ({', '.join(moves)}, then Enter; the side list "
        f"{list_frame}, chosen {chosen}); no value is said")
    return {"row_frame": row_frame, "list_frame": list_frame, "moves": moves, "chosen_frame": chosen,
            "panel_frame": cam.frame.path.name}


def to_reset_row(cam, cycle, model, profile: str):
    """MENU, the row by the scan, the carousel to the profile, Right into its settings, Down to Reset."""
    from mode_switch import find, open_menu
    from prove_run import Failed
    from proving.nav import find_row
    open_menu(cam)
    find(cam, cycle, model, ROW)
    to_profile(cam, profile)
    if not find_row(cam, RESET_ROW):
        raise Failed(f"no {RESET_ROW} row in {profile}'s settings ({cam.frame.path.name})")


def question_second(cam, profile: str) -> tuple:
    """(why the vision model's reading of the question refuses it, or "", its reading as words): asked once per frame
    (PROMPTS["notice"]); a question it reads as naming another profile refuses. Unreachable, or naming no profile: ""
    (the strict text guard, safety.profile_reset_dialog, decides)."""
    v = second_answer(cam, "notice")
    if v is None:
        return "", None
    said = " ".join(str(v.get("text") or "").split())
    others = [p for p in question_names(v) if p != profile]
    if others:
        return f"the vision model reads the question as naming {', '.join(others)} ({said!r}), not {profile} alone", said
    return "", said


def dialog(cam, profile: str, tries: int = 2, need_both: bool = False) -> dict:
    """The screen after Reset was opened: its frame, kind, text, lit button, the vision model's reading ("second"),
    how it was judged ("readers": question_readers), and why it is not the profile's own question ("" when it is): the
    strict text guard (safety.profile_reset_dialog) and the vision model's reading (question_second); with
    `need_both`, a vision reading that does not name the profile (not reachable, nothing parseable) refuses too. A
    screen not read as that question is looked at once more before it counts."""
    from camkit.live import lit_text, text_of
    for i in range(tries):
        kind, text, second, readers = cam.read().kind, " ".join(text_of(cam).split()), None, None
        if kind in NOT_A_DIALOG:
            why = f"the screen reads as {kind!r}, not a question"
        else:
            why = safety.profile_reset_dialog(text, profile)
            seen_why, second = question_second(cam, profile)
            readers = question_readers(second_answer(cam, "notice"), profile)
            why = why or seen_why or (
                f"the vision model gave no reading of the question naming {profile} (not reachable, or nothing it "
                f"said names it): {NEED_BOTH}" if need_both and readers != "both" else "")
        if not why or i + 1 == tries:
            break
        time.sleep(0.5)
        cam.refresh("reset-question")
    return {"frame": cam.frame.path.name, "kind": kind, "text": text,
            "lit": lit_text(cam.frame.image, cam.frame.path).strip(), "second": second, "readers": readers, "why": why}


def row_judged(cam, profile: str, fresh: int = ROW_FRESH, wait: float = 0.5, need_both: bool = False) -> tuple:
    """(why the lit row is not `profile`'s own Reset under its own title, or "", the way the title was accepted:
    "title" or "both readers", or None). Each frame judged is a submenu whose lit row reads Reset alone and whose title
    is the profile's (safety.profile_reset_row with the vision model's reading of the title, asked of every frame
    judged: OCR's title as read, or OCR's with the digits' look-alikes and the vision model's agreeing; a vision
    reading of another profile refuses). Judged on the frame on screen, then, while it refuses, on up to `fresh` fresh
    frames `wait` seconds apart, no press in between; the frame that passes is the one on screen when this returns
    (the frame the press is judged on); each look is logged (pp_reset_row_judged). The second trial (2026-11-11,
    kit2_pp_reset_stills) read the same PP3 title as "PP3" on 00098 and 00108 and as "PРЗ" on the frames between: one
    frame decides nothing either way. With `need_both`, a frame on which the vision model's reading of the title does
    not name the profile (title_readers: not reachable, nothing parseable) refuses too."""
    from camkit.live import lit_text
    why, by = "", None
    for look in range(fresh + 1):
        kind, lit, t, second, by = cam.read().kind, None, None, None, None
        if kind != "submenu":
            why = f"the screen reads as {kind!r}, not its settings"
        else:
            lit, t, second = lit_text(cam.frame.image, cam.frame.path), title(cam), second_title(cam)
            why = safety.profile_reset_row(lit, t, profile, second)
            if not why and need_both and title_readers(second, profile) != "both":
                why = (f"the vision model gave no reading of the panel's title naming {profile} (not reachable, or "
                       f"nothing it said names it): {NEED_BOTH}")
            by = None if why else safety.profile_reset_title(t, profile, second)[1]
        cam.run.log("pp_reset_row_judged", profile=profile, frame=cam.frame.path.name, look=look + 1, screen=kind,
                    lit=lit, title=t, second=second, why=why, by=by)
        if not why:
            return "", by
        if look < fresh:
            time.sleep(wait)
            cam.refresh("reset-row")
    return why, None


def open_reset(cam, profile: str, key: str = "right", need_both: bool = False) -> dict:
    """On the panel with Reset lit: judged (row_judged) and opened with `key`, that one row lifted for that one press
    (reset_lifted: the camera judges the press on the same frame, the lit row reading Reset alone and the title passing
    the same check, or refuses it); returns the screen after it (dialog), not yet judged by the caller. Stops with no
    press when no frame shows the lit row as Reset alone under the profile's own title."""
    from prove_run import Failed
    why, by = row_judged(cam, profile, need_both=need_both)
    if why:
        raise Failed(f"{profile}: {why} ({cam.frame.path.name}, the last of {ROW_FRESH + 1} frames looked at): Reset "
                     "not opened")
    row_frame = cam.frame.path

    readers = title_readers(second_title(cam), profile)

    def exact(frame, lit) -> bool:
        return (Path(frame.path) == Path(row_frame)
                and safety.profile_reset_row(lit, title(cam), profile, second_title(cam)) == ""
                and (not need_both or title_readers(second_title(cam), profile) == "both"))
    with reset_lifted(cam, exact):
        cam.press(key)
    return {**dialog(cam, profile, need_both=need_both), "row_frame": row_frame.name, "row_by": by,
            "row_readers": readers}


def to_ok(cam, d: dict, profile: str, need_both: bool = False) -> dict:
    """The question with OK lit. OK is lit when the a1 II's question opens (the peeks, 2026-11-11). If it is not: only
    Up and Down (MOVES; never Left or Right, which can select), at most two moves, the question read on a fresh frame
    before and after each and judged whole again each time (dialog: the text guard and the vision model); OK still not
    lit, a lit item that is neither OK nor Cancel, or a question that no longer passes: MENU and the run stops."""
    def ok(d) -> bool:
        if d["why"]:
            back_out(cam, f"{profile}: {d['why']}")
        if OK_BUTTON.fullmatch(d["lit"] or ""):
            return True
        if not CANCEL_BUTTON.fullmatch(d["lit"] or ""):
            back_out(cam, f"{profile}: the question lights {d['lit']!r}, neither OK nor Cancel")
        return False
    if ok(d):
        return d
    for key in MOVES:
        cam.refresh("reset-question")
        d = {**d, **dialog(cam, profile, tries=1, need_both=need_both)}
        if ok(d):
            return d
        cam.press(key)
        cam.refresh("reset-question")
        d = {**d, **dialog(cam, profile, tries=1, need_both=need_both)}
        if ok(d):
            return d
    back_out(cam, f"{profile}: OK never lit on the question ({' then '.join(MOVES)} tried)")


def back_on_panel(cam, profile: str, looks: int = 3, need_both: bool = False) -> dict:
    """Whether `profile`'s settings are back on screen after MENU or OK: a submenu whose title is the profile's. The
    vision model reads the title of every look (second_title); one that names another profile is not back. Otherwise:
    OCR's title as read (safety.profile_title: "title"); OCR's with the digits' look-alikes (title_names) and the vision
    model's agreeing ("both readers"), or, the vision model unreachable or reading no name, OCR's alone ("title with
    look-alikes", as before); a title OCR reads as no profile and the vision model as this one ("second reader"). A
    title read as another profile, or another kind of screen, is not. Looked at up to `looks` times, a fresh frame each.
    This check guards no press (what follows it is MENU and a download), so it may take what the guard before Reset
    never does. With `need_both` (the verify pass under --need-both-readers) a look confirms only when the vision
    model's reading of the title names the profile too (title_readers: "both"). Returns {"back": "confirmed" or
    "unconfirmed", "by" (how, or None), "frame", and "looks", what each look read: frame, kind, title, second}."""
    seen = []
    for i in range(looks):
        kind = cam.read().kind
        t = title(cam) if kind == "submenu" else ""
        look = {"frame": cam.frame.path.name, "kind": kind, "title": t}
        by = None
        if kind == "submenu":
            second = second_title(cam)
            look["second"] = second
            vname = title_names(second) if second else None
            named = title_names(t)
            if any(n != profile for n in safety.profile_names_in(second) + safety.profile_names_in(t)):
                by = None                    # either reader naming another profile anywhere: not back
            elif safety.profile_title(t, profile):
                by = "title"
            elif named == profile:
                by = "both readers" if vname == profile else "title with look-alikes"
            elif named is None and vname == profile:
                by = "second reader"
            if by and need_both and title_readers(second, profile) != "both":
                by = None                    # both readers needed: the vision model's reading must name it too
        seen.append(look)
        if by:
            return {"back": "confirmed", "by": by, "frame": cam.frame.path.name, "looks": seen}
        if i + 1 < looks:
            time.sleep(0.5)
            cam.refresh("back-on-panel")
    return {"back": "unconfirmed", "by": None, "frame": cam.frame.path.name, "looks": seen}


def complete_second(cam) -> str | None:
    """The vision model's reading of the screen after OK (PROMPTS["notice"], second_answer's cache: once a frame), its
    text and buttons as one text ("Complete. OK"); None when it is not reachable."""
    v = second_answer(cam, "notice")
    if v is None:
        return None
    buttons = v.get("buttons")
    buttons = buttons if isinstance(buttons, list) else [buttons] if buttons else []
    return " ".join(" ".join([str(v.get("text") or "")] + [str(b) for b in buttons]).split())


def complete_judged(cam) -> dict:
    """The screen on show judged as the completion notice (safety.profile_reset_complete: OCR's whole text and lit
    button, and the vision model's reading): {"frame", "kind", "text", "lit", "second", "why"}, why "" when it is that
    notice. A menu, a panel, the Main tiles or the shooting screen is no notice."""
    from camkit.live import lit_text, text_of
    kind = cam.read().kind
    look = {"frame": cam.frame.path.name, "kind": kind, "text": " ".join(text_of(cam).split()), "lit": None,
            "second": None}
    if kind in NOT_A_DIALOG:
        return {**look, "why": f"the screen reads as {kind!r}, not a notice"}
    look["lit"] = lit_text(cam.frame.image, cam.frame.path).strip()
    look["second"] = complete_second(cam)
    return {**look, "why": safety.profile_reset_complete(look["text"], look["lit"], look["second"])}


def after_ok(cam, profile: str, looks: int = AFTER_OK_LOOKS) -> dict:
    """The screen Enter on the accepted question led to: {"seen": "notice"} with the notice's look (complete_judged)
    when it is the camera's completion notice ("Complete." and OK, the a1 II's, 00043_enter.png of
    kit2_pp_reset_trial); {"seen": "panel", "back"} when it is the profile's settings straight away, confirmed
    (back_on_panel: another body or firmware may show no notice); else {"seen": "unknown", "why", and the last look},
    which the caller stops on. A screen that is neither is looked at on `looks` frames in all (a fresh one between, no
    press), so a frame caught mid-change decides nothing; a panel back_on_panel cannot confirm is unknown at once
    (back_on_panel has looked three times). Every look is kept ("looks")."""
    seen = []
    for i in range(looks):
        if cam.read().kind == "submenu":
            back = back_on_panel(cam, profile)
            if back["back"] == "confirmed":
                return {"seen": "panel", "back": back, "looks": seen + back["looks"]}
            last = back["looks"][-1]
            return {"seen": "unknown", "looks": seen + back["looks"], **last, "text": last.get("title", ""),
                    "lit": None, "second": last.get("second"),
                    "why": f"a panel whose title is not {profile}'s ({looks_said(back)})"}
        look = complete_judged(cam)
        seen.append(look)
        cam.run.log("pp_reset_complete_judged", profile=profile, look=i + 1, screen=look["kind"],
                    **{k: v for k, v in look.items() if k != "kind"})
        if not look["why"]:
            return {"seen": "notice", **look, "looks": seen}
        if i + 1 < looks:
            time.sleep(0.5)
            cam.refresh("after-ok")
    return {"seen": "unknown", **seen[-1], "looks": seen}


def stop_after_ok(cam, profile: str, ok_frame: str, after: dict, why: str | None = None):
    """An unknown screen after OK (or after the completion notice was dismissed): its words logged
    (pp_reset_after_ok), MENU on it when it is a dialog or notice (nothing else is pressed), and the run stops: what
    follows OK on a reset is nothing to carry on from unless it is known. The session's end closes the camera and
    puts the start file back, the profile with it."""
    from prove_run import Failed
    why = why or after["why"]
    cam.run.log("pp_reset_after_ok", profile=profile, frame=after.get("frame"), screen=after.get("kind"),
                text=after.get("text"), lit=after.get("lit"), second=after.get("second"), why=why,
                looks=after.get("looks"))
    if cam.read().kind not in NOT_A_DIALOG:
        cam.press("menu")
    raise Failed(f"{profile}: after OK on the accepted question ({ok_frame}) the camera showed neither its completion "
                 f"notice nor {profile}'s settings: {why} ({after.get('frame')}, read {after.get('text')!r}; the "
                 f"vision model {after.get('second')!r}): MENU only, and the run stops; whether {profile} was reset is "
                 "not known (the start file goes back on)")


def dismiss_complete(cam, profile: str, ok_frame: str, notice: dict) -> str:
    """The completion notice closed the kit's way for a notice that asks nothing (proving.nav.to_shooting, the
    session's cleanup): MENU, which the a1 II took on this very notice back to the profile's settings (kit2_pp_reset_trial
    00045 then 00046_cancel.png); OK only when the camera refuses MENU, on the notice read afresh and judged again
    (complete_judged) and passed by drive.py's own Enter guard as a notice, never as a confirmation. Returns the key
    that closed it."""
    import drive
    from camkit.link import LinkError
    try:
        cam.press("menu")
        return "menu"
    except LinkError as e:
        cam.run.log("pp_reset_complete_menu_refused", profile=profile, frame=cam.frame.path.name, why=str(e)[:300])
    time.sleep(0.5)
    cam.refresh("complete-notice")
    again = complete_judged(cam)
    if again["why"]:
        stop_after_ok(cam, profile, ok_frame, {**again, "looks": [notice, again]},
                      f"MENU refused on the completion notice, and then {again['why']}")
    why = drive.press_refused("enter", again["lit"], again["text"], again["kind"])
    if why:
        stop_after_ok(cam, profile, ok_frame, {**again, "looks": [notice, again]},
                      f"MENU refused on the completion notice, and OK refused: {why}")
    cam.press("enter")
    return "enter"


def looks_said(back: dict) -> str:
    """What back_on_panel's looks read, in words for the console."""
    return "; ".join(f"{x['frame']}: {x['kind']}" + (f", title {x['title']!r}" if x.get("title") else "")
                     + (f", the second reader {x['second']!r}" if x.get("second") is not None else "")
                     for x in back["looks"])


def reset_one(cam, cycle, model, profile: str, say, open_key: str = "right", need_both: bool = False) -> dict:
    """Step 2 for one profile, up to OK, the screen after it and the look for its settings. After OK the camera's
    completion notice is expected (after_ok: "Complete." and OK, read so by OCR and by the vision model): it is kept
    ("complete": true, its frame), closed (dismiss_complete: MENU, OK only if MENU is refused) and the profile's
    settings looked for. The settings straight back, confirmed, are taken too ("complete": false). Anything else after
    OK (another notice, a question, an error, a panel of another title): MENU only and the run stops (stop_after_ok),
    the profile not counted. Returns its frames, the question as read, "complete", and "back": "confirmed", or
    "unconfirmed" when, after the completion notice was closed, no look showed the profile's settings (back_on_panel):
    that one does not stop the run, since the camera said the reset was complete; what was read is said and kept, the
    download after it closes the screen with MENU, and the next profile starts from the shooting screen as every
    profile does (MENU, the row by the scan, the carousel read)."""
    import drive
    from camkit.live import text_of
    to_reset_row(cam, cycle, model, profile)
    d = open_reset(cam, profile, open_key, need_both=need_both)
    if d["why"]:
        back_out(cam, f"{profile}: {d['why']}")
    d = to_ok(cam, d, profile, need_both=need_both)
    if d["frame"] != cam.frame.path.name:
        back_out(cam, f"{profile}: the question was judged on {d['frame']}, not the frame on screen")
    why = drive.press_refused("enter", d["lit"], d["text"], d["kind"], confirm=True)
    if why:
        back_out(cam, f"{profile}: Enter refused: {why}")
    ok_frame = cam.frame.path.name
    cam.press("enter")
    after = after_ok(cam, profile)
    if after["seen"] == "unknown":
        stop_after_ok(cam, profile, ok_frame, after)
    complete, closed_by = after["seen"] == "notice", None
    if complete:
        closed_by = dismiss_complete(cam, profile, ok_frame, after)
        back = back_on_panel(cam, profile)
        notice = f", the camera's completion notice {after['frame']} closed with {closed_by.upper()}"
    else:
        back, notice = after["back"], ", no completion notice"
    if back["back"] == "confirmed":
        how = "" if back["by"] == "title" else f" ({back['by']}: {looks_said(back)})"
        say(f"{profile}: reset (question {d['frame']}, OK {ok_frame}{notice}, back on its settings "
            f"{back['frame']}{how})")
    else:                                   # only after the completion notice: after_ok stops on any other screen
        kind = cam.read().kind
        cam.run.log("pp_reset_after_ok", profile=profile, frame=cam.frame.path.name, screen=kind,
                    text=" ".join(text_of(cam).split()), complete_frame=after["frame"], looks=back["looks"])
        say(f"{profile}: OK pressed on the accepted question ({d['frame']}, OK {ok_frame}{notice}), but {profile}'s "
            f"settings were not seen back after it ({looks_said(back)}; the screen's words are in the run's "
            "events.jsonl): counted as reset, the camera said Complete; back unconfirmed; MENU out and the download, "
            "then the next profile from the shooting screen")
    return {"profile": profile, "row_frame": d["row_frame"], "row_by": d.get("row_by"),
            "readers": {"title": d.get("row_readers") or "ocr", "question": d.get("readers") or "ocr"},
            "question_frame": d["frame"],
            "question": d["text"], "question_second": d.get("second"), "question_kind": d["kind"],
            "ok_frame": ok_frame, "complete": complete, "complete_frame": after["frame"] if complete else None,
            "complete_text": after["text"] if complete else None,
            "complete_second": after["second"] if complete else None, "complete_closed_by": closed_by,
            "back": back["back"], "back_by": back["by"], "back_frame": back["frame"], "back_looks": back["looks"]}


def verify_pass(cam, link, cycle, model, done: list, run, say, need_both: bool = False) -> dict:
    """Step 3: every profile reset entered once more (MENU, the row by the scan, the carousel to it, Right into its
    settings: to_profile), the panel confirmed as the profile's own as the reset path confirms it (back_on_panel; with
    `need_both`, the vision model's reading of the title naming the profile too), and left with MENU (close_screen's
    cleanup presses), no Reset opened; a STOP file looked for before each. Returns {profile: "confirmed" or
    "unconfirmed"} (an unconfirmed panel guards no press, so the pass goes on; the caller counts the run not
    verified). The download after it (the caller's) says whether entering a panel alone moves the profiles'
    parameters: "changed between two downloads" is not "written by the reset" until it does not."""
    from camkit.link import StopRequested
    from mode_switch import find, open_menu
    from runner import close_screen
    entered = {}
    for p in done:
        if run.stop_requested():
            raise StopRequested(f"{run.stop_reason()}: stopped in the verify pass before {p}")
        open_menu(cam)
        find(cam, cycle, model, ROW)
        to_profile(cam, p)
        back = back_on_panel(cam, p, need_both=need_both)
        entered[p] = back["back"]
        cam.run.log("pp_reset_verify_entered", profile=p, back=back["back"], by=back["by"], frame=back["frame"],
                    looks=back["looks"], need_both=need_both)
        if back["back"] != "confirmed":
            say(f"verify pass: the panel Right on {p} opened was not confirmed as {p}'s ({looks_said(back)})")
        close_screen(cam, link)
    n = sum(1 for x in entered.values() if x == "confirmed")
    say(f"verify pass: {len(done)} profiles entered and left with MENU, no Reset opened; {n} of {len(done)} panels "
        "confirmed as the profile's")
    return entered


def changed_keys(a: Path, b: Path) -> list:
    """The record keys whose bytes differ between two downloads (ids only; the volatile records left out)."""
    return [c.key for c in camset.diff(camset.read(a), camset.read(b))]


def in_run(run_dir: Path, p: Path) -> str:
    """A download as the result keeps it: relative to the run folder when inside it."""
    try:
        return Path(p).resolve().relative_to(Path(run_dir).resolve()).as_posix()
    except ValueError:
        return Path(p).as_posix()


def split(keys: list, family: set) -> tuple:
    """(the keys of the profiles' parameters, the others), ids only."""
    fam = [k for k in keys if k.startswith("global:") and int(k.split(":0x")[1], 16) in family]
    return fam, [k for k in keys if k not in fam]


def choose(offered: list, asked: list, recorded=None) -> tuple:
    """(the profiles to reset, the profiles the camera's list offers, a line for the console or ""), the list judged
    as a whole before any reset. Every label must be Off, a profile or a kind left alone (label_kind; read_profiles
    has asked the second reader already); no profile may come twice (a misread: PP10 read as PP1); a profile asked for
    must be on the list; and where the recorded walk lists the profiles, the camera's must be the same ones, else the
    run stops unless --profiles names exactly the ones to reset (another body or firmware may offer others)."""
    from prove_run import Failed
    unread = [x for x in offered if label_kind(x)[0] == "unread"]
    if unread:
        raise Failed(f"the camera's {ROW} list holds {', '.join(repr(x) for x in unread)}, which reads as neither Off, "
                     "a profile (PP and a number) nor User1-User4: the run stops before any reset rather than skip it")
    have = [p for p in (profile_of(x) for x in offered) if p]
    twice = [p for p in dict.fromkeys(have) if have.count(p) > 1]
    if twice:
        raise Failed(f"the camera's {ROW} list reads {', '.join(twice)} more than once ({', '.join(offered)}): an "
                     "option was misread, so the list is not known; nothing was reset. Run again, and look at the "
                     "carousel's frames if it happens again")
    missing = [p for p in asked if p not in have]
    if missing:
        raise Failed(f"--profiles {', '.join(missing)}: not on the camera's {ROW} list ({', '.join(have) or 'none'})")
    todo = [p for p in have if not asked or p in asked]
    if not todo:
        raise Failed(f"the camera's {ROW} list offers no profile (PP and a number) to reset")
    note = ""
    if recorded is not None and set(have) != set(recorded):
        gone, new = [p for p in recorded if p not in have], [p for p in have if p not in recorded]
        diff = "; ".join(x for x in (f"the walk's {', '.join(gone)} not on the camera" if gone else "",
                                     f"the camera's {', '.join(new)} not in the walk" if new else "") if x)
        said = (f"the camera's {ROW} list ({', '.join(have)}) is not the recorded walk's ({', '.join(recorded) or 'none'}):"
                f" {diff}")
        if not asked:
            raise Failed(f"{said}. Nothing was reset. Another body or firmware may offer other profiles, or a label was "
                         "misread: look at the carousel's frames in the run folder, then run again with --profiles "
                         f"naming exactly the profiles to reset (--profiles {','.join(have)} for the camera's list)")
        note = f"{said}: --profiles names the ones to reset, {', '.join(todo)}"
    return todo, have, note


def start_mode(camera: str, start: Path) -> str | None:
    """The shooting mode the start file was saved in, as the camera's definition reads it (camera.live_mode,
    make_sample.file_mode), or None when the definition names none: the start download is the session's own, so this
    is no new traffic to the camera."""
    import make_sample
    f = definitions.DIR / f"{camera}.json"
    if not f.exists():
        return None
    return make_sample.file_mode(json.loads(f.read_text(encoding="utf-8")), camset.read(start))


def need_both_of(a, asked) -> bool:
    """--need-both-readers: on unless the run is a peek or limited by --profiles; --need-both-readers turns it on
    and --ocr-alone-ok off whatever the run."""
    if getattr(a, "ocr_alone_ok", False):
        return False
    return bool(getattr(a, "need_both_readers", False)) or not (a.peek or asked)


def control_profile_of(a, todo: list, asked: list) -> str | None:
    """The profile the positive control is made on (--control-profile, else the first to reset), or None (a peek,
    --no-control)."""
    from prove_run import Failed
    if a.peek or getattr(a, "no_control", False):
        return None
    cp = getattr(a, "control_profile", None) or todo[0]
    if cp not in todo:
        raise Failed(f"--control-profile {cp}: not among the profiles this run resets ({', '.join(todo)}): nothing "
                     "pressed")
    return cp


def run_session(a, camera: str, mode: str, asked: list, recorded, allowance: str) -> int:
    from camkit.frames import eyes_from_config
    from camkit.link import StopRequested
    from camkit.runs import Run
    from memreg_run import download
    from prove_run import Failed
    from runner import load_scan, prover_session
    cycle, model = load_scan(in_mode(a.scan, mode))
    run = Run(a.run or default_run(mode))
    hdmi = eyes_from_config(run)
    say = lambda m: print(m, flush=True)     # noqa: E731
    family = family_ids(camera)
    cmap = family_copies(camera)
    need_both = need_both_of(a, asked)
    out = run.dir / (PEEK_RESULT if a.peek else RESULT)
    result = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "camera": camera, "mode": mode, "family": FAMILY,
              "scan": scan_dir(in_mode(a.scan, mode)).name, "allowance": allowance, "peek": bool(a.peek),
              "asked": list(asked) or None, "need_both_readers": need_both, "profiles": [], "completion_notice": 0,
              "no_notice": 0, "control": None, "last": None, "finished": False, "verified": None}
    if not a.peek and getattr(a, "no_control", False):
        result["control_skipped"] = "--no-control (a --profiles trial): this result can never feed the sample"
    with prover_session(run, hdmi, show=0, end_why="the settings download after the resets") as s:
        cam, link = s.cam, s.link
        result["start"] = in_run(run.dir, s.start)
        write_json(out, result, indent=1)
        try:
            result["start_mode"] = start_mode(camera, s.start)
            if result["start_mode"] not in (None, mode):
                raise Failed(f"the start file was saved in {result['start_mode']} mode, not {mode} (--in {mode}): "
                             "nothing pressed. Put the camera in the mode --in names, or name its mode")
            kept = {}
            offered = read_profiles(cam, link, cycle, model, say, kept=kept)
            result["offered"] = offered
            result["labels_single_reader"] = kept.get("single", [])
            result["labels_single_reader_note"] = (
                "the carousel's labels guard no press (the panel's title and the question do); a label read by one "
                "reader alone, Off and User1-User4 among them, is taken as read")
            todo, have, note = choose(offered, asked, recorded)
            result["offered_profiles"] = have
            if note:
                say(note)
            cp = control_profile_of(a, todo, asked)
            if cp:
                todo = [cp] + [p for p in todo if p != cp]       # the control's profile is reset first
            if a.peek:
                result["peek_of"] = peek(cam, link, hdmi, cycle, model, todo[0], s.start, family, say, a.open_key)
                result["finished"] = True
            else:
                prev = s.start
                if cp:
                    if run.stop_requested():
                        raise StopRequested(f"{run.stop_reason()}: stopped before the control")
                    result["control"] = {"profile": cp, "parameter": CONTROL_ROW, "ok": None}
                    write_json(out, result, indent=1)
                    result["control"].update(control_change(cam, cycle, model, cp, say))
                    write_json(out, result, indent=1)
                    if run.stop_requested():
                        raise StopRequested(f"{run.stop_reason()}: stopped after the control's change")
                    got = download(cam, link, hdmi, CONTROL_TAG)
                    fam, other = split(changed_keys(s.start, got), family)
                    c = result["control"]
                    c.update(download=in_run(run.dir, got), changed=fam, copies_changed=copies(fam, cmap))
                    write_json(out, result, indent=1)
                    say(f"control: {len(fam)} of the profiles' parameters changed since the start file "
                        f"({', '.join(fam) or 'none'}; {copies_said(c['copies_changed'])}), {len(other)} others; "
                        f"download {got.name}")
                    if not fam:
                        c["ok"] = False
                        raise Failed(f"control: moving {cp}'s {CONTROL_ROW} by one step changed none of the profiles' "
                                     "parameters in the download: what a Reset writes cannot be shown; the run stops "
                                     "before any reset")
                    el = control_elements(camera, s.start, got, cp, mode)
                    if el["others"] or el["missing"]:
                        c["ok"] = False
                        raise Failed("control: " + (
                            f"the change moved more than {cp}'s element of {', '.join(el['others'])} (another "
                            f"profile's element, or a record that holds none for {cp})" if el["others"] else
                            f"the change moved no {' and no '.join(el['missing'])} record of the profiles' parameters")
                            + ": a control moves one parameter of one profile, in use and in this mode's copy; the "
                              "run stops before any reset")
                    control_file = prev = got
                for p in todo:
                    if run.stop_requested():       # between profiles, never with a dialog open
                        raise StopRequested(f"{run.stop_reason()}: stopped before {p}")
                    entry = reset_one(cam, cycle, model, p, say, a.open_key, need_both=need_both)
                    got = download(cam, link, hdmi, f"reset-{p}")
                    keys = changed_keys(prev, got)
                    fam, other = split(keys, family)
                    entry.update(download=in_run(run.dir, got), changed=keys, family_changed=fam)
                    result["profiles"].append(entry)
                    result["completion_notice"] = sum(1 for e in result["profiles"] if e.get("complete"))
                    result["no_notice"] = len(result["profiles"]) - result["completion_notice"]
                    result["last"] = in_run(run.dir, got)
                    write_json(out, result, indent=1)
                    say(f"{p}: {len(keys)} records changed since the download before it: {len(fam)} of the profiles' "
                        f"parameters, {len(other)} others ({', '.join(other) or 'none'}); download {got.name}"
                        + (" (back unconfirmed)" if entry.get("back") == "unconfirmed" else "")
                        + ("" if entry.get("complete") else " (no completion notice: its settings came straight back)"))
                    if cp and p == cp:
                        c = result["control"]
                        wrote = control_wrote(camera, control_file, got, cp, c["changed"])
                        c.update(reset_download=in_run(run.dir, got), reset_wrote=wrote,
                                 copies_reset_wrote=copies(wrote, cmap), ok=wrote == c["changed"])
                        write_json(out, result, indent=1)
                        say(f"control: {p}'s Reset wrote {len(wrote)} of the {len(c['changed'])} records the control "
                            f"changed ({copies_said(c['copies_reset_wrote'])})")
                        if not c["ok"]:
                            left = [k for k in c["changed"] if k not in wrote]
                            raise Failed(f"control: {p}'s Reset left {p}'s element of {', '.join(left)} as the control "
                                         "set it: the Reset is not shown to write the records a settings file saves; "
                                         "the run stops")
                    prev = got
                done = [e["profile"] for e in result["profiles"]]
                whole = bool(asked) or (len(done) == len(have) and set(done) == set(have))
                if not whole:                # every profile the list offers, or the run has not finished
                    result["stopped"] = "not every profile the camera offered was reset"
                if done:
                    entered = verify_pass(cam, link, cycle, model, done, run, say, need_both=need_both)
                    got = download(cam, link, hdmi, "verify")
                    keys = changed_keys(prev, got)
                    fam, other = split(keys, family)
                    unsure = [p for p in done if entered.get(p) != "confirmed"]
                    result["verify"] = {"download": in_run(run.dir, got), "family_changed": fam,
                                        "others_changed": len(other), "entered": entered}
                    result["verified"] = bool(family) and not fam and not unsure
                    write_json(out, result, indent=1)
                    say(f"verify: {len(fam)} of the profiles' parameters changed between the last reset's download and "
                        f"the verify download ({', '.join(fam) or 'none'}), {len(other)} others; download {got.name}"
                        + ("" if family else "; the definition names no profiles' parameters, so nothing is verified")
                        + (f"; entered without the panel confirmed as the profile's: {', '.join(unsure)}, so not "
                           "verified" if unsure else ""))
                result["finished"] = whole   # only now: a failure in the verify pass is no finished run
        except BaseException as e:           # said and kept; prover_session closes the camera and restores
            result["stopped"] = f"{type(e).__name__}: {e}"
            result["finished"] = False
            raise
        finally:
            write_json(out, result, indent=1)
    result["restored"] = s.restored
    write_json(out, result, indent=1)
    have = result.get("offered_profiles")
    counts = (f"the camera offered {len(have)} profiles ({', '.join(have)})" if have is not None
              else "the camera's list was not read") + f", {len(result['profiles'])} reset" + (
        f" (--profiles {', '.join(asked)})" if asked else "")
    c = result.get("control")
    if c:
        counts += ("; control: " + (
            f"{c['profile']}'s {CONTROL_ROW} changed {len(c['changed'])} records, its Reset wrote all of them back"
            if c.get("ok") else "NOT shown (" + (
                "the change was not made" if c.get("changed") is None else
                "the change moved none of the profiles' parameters" if not c["changed"] else
                f"its Reset wrote {len(c.get('reset_wrote') or [])} of {len(c['changed'])}" if "reset_wrote" in c else
                "the run stopped before the Reset") + "): make_sample refuses this result"))
    elif not a.peek:
        counts += ("; no control (--no-control)" if getattr(a, "no_control", False) else
                   "; no control made (the run stopped before it)") + ": make_sample refuses this result"
    unsure = [e for e in result["profiles"] if e.get("back") == "unconfirmed"]
    if unsure:
        result["back_unconfirmed"] = [e["profile"] for e in unsure]
        write_json(out, result, indent=1)
        counts += (f"; {len(unsure)} not seen back on their settings after OK, counted as reset since OK was pressed on "
                   f"the accepted question ({', '.join(e['profile'] + ' ' + e['back_frame'] for e in unsure)}): look "
                   "at those frames and each one's changed records")
    if not a.peek and result["profiles"]:
        v = result.get("verify") or {}
        unsure = [p for p, x in (v.get("entered") or {}).items() if x != "confirmed"]
        why = "; ".join(x for x in (", ".join(v.get("family_changed") or []),
                                    f"panel not confirmed: {', '.join(unsure)}" if unsure else "") if x)
        counts += ("; verified: entering the panels again, each confirmed as its profile's, moved none of the "
                   "profiles' parameters" if result["verified"] else
                   f"; NOT verified ({why or 'no verify download'}): make_sample refuses this result")
    if not a.peek and result["profiles"]:
        n = result["completion_notice"]
        counts += (f"; {n} of {len(result['profiles'])} showed the camera's completion notice"
                   + (f", {len(result['profiles']) - n} came straight back to their settings with none (make_sample "
                      "refuses this result unless --allow-no-notice)" if n < len(result["profiles"]) else ""))
        alone = [e["profile"] for e in result["profiles"]
                 if (e.get("readers") or {}).get("title") != "both" or (e.get("readers") or {}).get("question") != "both"]
        if alone:
            counts += (f"; judged on OCR's reading alone before Reset or OK: {', '.join(alone)} (make_sample refuses "
                       "this result)")
    if result["finished"] and not a.peek:
        say(f"finished: {counts}; the last download, every one reset: {result['last']} (in {run.dir.name}); the start "
            "file is back on the camera, checked" if s.restored else
            f"finished: {counts}; the start file was uploaded but the restore was NOT checked")
    elif not result["finished"]:
        say(f"stopped ({result.get('stopped', 'unknown')}): {counts} before it; the start file went back on the camera "
            f"({'checked' if s.restored else 'NOT checked'}); {paths.shown(out)} holds what was done")
    control_ok = a.peek or getattr(a, "no_control", False) or (c or {}).get("ok") is True
    good = result["finished"] and s.restored and (a.peek or result["verified"] is True) and control_ok
    return 0 if good else 1


def copies_said(n: dict | None) -> str:
    """A copies count in words: "in use 1, stills 1, movie 0"."""
    if not n:
        return "the copies not told apart: no definition"
    return f"in use {n.get('in_use', 0)}, stills {n.get('stills', 0)}, movie {n.get('movie', 0)}"


def peek(cam, link, hdmi, cycle, model, profile: str, start: Path, family: set, say, open_key: str = "right") -> dict:
    """--peek: the profile's Reset opened, the screen recorded, MENU (cancel), its settings checked back, a download
    and the keys changed since the start (opening must reset nothing: none of the profiles' parameters)."""
    from memreg_run import download
    to_reset_row(cam, cycle, model, profile)
    d = open_reset(cam, profile, open_key)
    lit = d["lit"]
    button = "OK" if OK_BUTTON.fullmatch(lit) else ("Cancel" if CANCEL_BUTTON.fullmatch(lit) else "neither")
    say(f"{profile}'s Reset opened: {d['kind']} on {d['frame']}, lit {lit!r} ({button}), reading {d['text']!r}")
    say(f"   the guards {'accept it' if not d['why'] else 'refuse it: ' + d['why']}")
    if d["kind"] not in NOT_A_DIALOG:
        cam.press("menu")                    # cancel, never OK
    seen = back_on_panel(cam, profile)
    back = seen["back"] == "confirmed"
    where = (f"back on {profile}'s settings" + ("" if seen["by"] == "title" else f" ({seen['by']})") if back
             else "NOT seen back on the profile's settings")
    say(f"   MENU: {where} ({cam.frame.path.name}; {looks_said(seen)})")
    got = download(cam, link, hdmi, "after-peek")
    keys = changed_keys(start, got)
    fam, other = split(keys, family)
    say(f"   since the start: {len(keys)} records changed, {len(fam)} of the profiles' parameters"
        f"{' (opening Reset changed them: do not run the resets)' if fam else ''}; others: {', '.join(other) or 'none'}")
    return {**d, "profile": profile, "button": button, "accepted": not d["why"], "back_on_panel": back,
            "back_by": seen["by"], "back_frame": seen["frame"], "back_looks": seen["looks"], "download": got.name,
            "changed": keys, "family_changed": fam}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    add_allow_argument(ap)
    add_in_argument(ap)
    ap.add_argument("--scan", default=LATEST_SCAN, type=scan_arg,
                    help="the page scan of the menu the camera shows now (default: the camera's latest page scan made "
                         "in the mode --in names, runner.latest_scan)")
    ap.add_argument("--profiles", action="append", default=[], help="profiles to reset, comma-separated (default: "
                                                                     "every PP profile the camera's list offers)")
    ap.add_argument("--run", default=None, help="the run folder (default: kit2_pp_reset_stills or kit2_pp_reset_movie)")
    ap.add_argument("--open-key", choices=OPEN_KEYS, default="right",
                    help="the key that opens the Reset row (Right, as the card rows open; Enter if a peek shows Right "
                         "does not)")
    ap.add_argument("--peek", action="store_true", help="open the first profile's Reset, record its question, cancel")
    ap.add_argument("--control-profile", default=None,
                    help=f"the profile the positive control moves {CONTROL_ROW} on, one step, before the resets "
                         "(default: the first profile to reset); it is reset first")
    ap.add_argument("--no-control", action="store_true",
                    help="no positive control: only with --peek or --profiles, and the result can never feed the "
                         "sample")
    both = ap.add_mutually_exclusive_group()
    both.add_argument("--need-both-readers", action="store_true",
                      help="refuse to open Reset or press OK on a title or question the vision model gave no reading "
                           "of (the default for a run that is not a peek and not limited by --profiles)")
    both.add_argument("--ocr-alone-ok", action="store_true",
                      help="let OCR alone judge the title and the question when the vision model gives no reading "
                           "(each profile's readers are kept; make_sample refuses such a result)")
    ap.add_argument("--dry-run", action="store_true", help="print the plan; no link")
    a = ap.parse_args(argv)
    allowance = allowance_of(a.allow)
    mode = a.in_mode
    if mode not in MODES:
        sys.exit(f"pp_reset_run: --in {mode}: this run works in {' or '.join(MODES)} mode, where the camera's "
                 "Picture Profile list was walked. Nothing was sent to the camera.")
    asked = asked_profiles(a.profiles)
    if a.no_control and not (a.peek or asked):
        sys.exit("pp_reset_run: --no-control only for a --peek or a --profiles trial: a run meant for the sample makes "
                 "the positive control. Nothing was sent to the camera.")
    control = None
    if a.control_profile is not None:
        if a.no_control or a.peek:
            sys.exit("pp_reset_run: --control-profile names the control's profile; a --peek or --no-control run makes "
                     "no control. Nothing was sent to the camera.")
        control = (asked_profiles([a.control_profile]) or [None])[0]
        if control is None or "," in a.control_profile:
            sys.exit(f"pp_reset_run: --control-profile {a.control_profile!r}: one profile's name (PP1). Nothing was "
                     "sent to the camera.")
        if asked and control not in asked:
            sys.exit(f"pp_reset_run: --control-profile {control} is not among --profiles {', '.join(asked)}. Nothing "
                     "was sent to the camera.")
        a.control_profile = control          # as the camera writes it (PP1), for run_session
    root = paths.run_root()
    camera = root.name
    scan = scan_dir(in_mode(a.scan, mode))
    place = scan_row(scan)
    recorded, where = recorded_profiles(camera, mode)
    run_dir = root / (a.run or default_run(mode))
    todo = [p for p in (recorded or []) if not asked or p in asked] or asked
    if not a.peek and not a.no_control:
        control = control or (todo[0] if todo else "the first profile")
    for line in plan_lines(camera, mode, scan, place, recorded, where, asked, run_dir, a.peek, control,
                           need_both_of(a, asked)):
        print(line, flush=True)
    if a.dry_run:
        print("dry run: nothing was sent to the camera", flush=True)
        return 0
    if place is None:
        sys.exit(f"pp_reset_run: the page scan {scan.name} has no {ROW} row: scan the {mode} menu again or name "
                 "another with --scan. Nothing was sent to the camera.")
    return run_session(a, camera, mode, asked, recorded, allowance)


if __name__ == "__main__":
    sys.exit(main())
