"""The coverage ledger: what is settled about a camera's menus and its file, so no session does the same work twice
(docs/decisions/0023).

One entry per menu row (mode, tab, group, row path), one per value of every setting (the options), and one per record
of the file, each with exactly one status (STATUSES, RECORD_STATUSES), in the order of precedence: an entry takes the
first status that applies. The ledger is GENERATED each time from the sources that already exist, so it cannot drift:

    the definition          menu, settings (proved, not_offered, unproved_reason, inactive_when, row, row_mode), and
                            with its private evidence the menu rows a proof went through (placement of an unplaced
                            setting; a row of no setting a proof went through takes the setting it proved)
    the hand tables         FRAME_PROOFS (a hand proof), MY_MENU_ROW (where the My Menu slots are set)
    the camera file         volatile_records, my_menu, save_load_excluded (Sony's Save/Load list, as data)
    camkit.safety           each row's class (never_open) and what opens it today (lift_class: --network; owner_class:
                            --owner; allow_refused: --allow; owner_may_approve: an approved motion decision; never)
    the Help Guide's list   the rows no scan has seen (another mode's, a tab the definition's menu lacks)

and, where they are on this computer (the mapper's own, never published):

    the looks file          private/evidence/<model>_fw<fw>/looks_<model>_fw<fw>.jsonl: RECORDED, append-only, one
                            line per look (kit/drive.py per --path, kit/crawl_run.py per row, kit/prove_run.py per row,
                            kit/tools/coverage.py --record for the owner's hand checks); never a value
    the runs                each run's rows.jsonl (crawl outcomes), proofs.jsonl, failures.jsonl, attempts.jsonl, the
                            page models (the latest scan of each mode: greyed rows), pass 2's report.json ("new"
                            records), kit2_pass1/map_all.json (the walked lists), downloads.jsonl and the latest
                            download (the record ids)
    the accepted rulings    private/evidence/<model>_fw<fw>/accepted_<model>_fw<fw>.json ("new" records)
    the leads               private/evidence/<model>_fw<fw>/leads_<model>_fw<fw>.json: which unmapped records ever
                            changed in the camera's own downloads, and the rows of the steps they changed in
                            (kit/tools/leads.py --write; never a value)

Two forms are written by kit/tools/coverage.py --write. The PUBLIC lean form, data/<model>_fw<fw>/coverage_<model>_
fw<fw>.json, is built from the public sources ALONE (load_sources(public=True): the definition without its evidence,
the hand tables, the camera file, the Help Guide's list, camkit.safety) and a short allow-list of what a look
establishes that is true of every camera of the model (ALLOWED: a row opens an information screen, with the kit's
address field names it showed, safety.ADDRESS_FIELDS'; a row acted when opened; a hand check changed a record; a row on
the maker's Save/Load list was seen to change nothing, "confirmed"). Those facts live in a small public file of their
own, the seen file, data/<model>_fw<fw>/seen_<model>_fw<fw>.json (schemas/coverage-seen.schema.json), which --write
writes where the looks file is on the computer (its facts with the looks' own, the looks' retractions taking committed
ones out): an edit of a fact shows in review as a change to that one small file, and the public form is always, byte
for byte, the build of the public sources and the seen file (public_build, build_problems, which check_public runs).
Nothing observed about the camera's state goes public: no "tested, no record changes", no "greyed in state" but the
definition's inactive_when, no "needs equipment" but an unproved_reason's, no "kit cannot read", never a run, date,
hash, frame, current option or value (public_problems and seen_problems, which kit/tools/check_public.py runs: the
schemas, a closed vocabulary and PRIVATE_KEYS). The PRIVATE form, beside the looks file, is the full build: each
status's citations, the proofs' validity and one evidence bundle per valid proof.

settled(): drive.py, crawl_run.py and prove_run.py ask it before they press on a row (the gates below), and by default
only PRINT what it says ("coverage: <row>: <status> ..."), from the private build made once a run, reading no download
and asking git nothing for it (judge=False). Only crawl_run.py and prove_run.py given --skip-settled leave a settled
row out; drive.py never does. A row with values still to try (values_left) is never settled; a row greyed before is
settled only while the start file still greys it (its inactive_when, or the blocker's records as they were when the
look started), a row the kit could not read (a deterministic failure) only while the kit's commit is the look's. Of the
looks, the latest of a row, what was done and the option wins, but a look that did not reach the row never takes the
place of one that did. Nothing is settled when the ledger cannot be built (no definition, or no looks file yet: the
first run on a camera) or is stale, and the run says so in one line. A ledger error never breaks a run: each gate says
it in one line and changes nothing.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from . import ROOT, definitions, jsonl, match, paths, safety

FORMAT = 1
# the mode the definition's menu was walked in (pass 1 runs in Stills: runner.SCAN_MODES' first); a setting's
# row_mode names another
MENU_MODE = "Stills"
OTHER_MODE = "Movie"

# ---------------------------------------------------------------- the statuses, in the order of precedence

STATUSES = (
    ("proved", "The definition's proved establishes it: an option's value is one its proof lists and no rule named "
               "from another setting's proof (privately read from the whole proof: chosen on the setting; publicly "
               "from a proof whose setting carries no proved.shared mark), or its setting's scale is proved on one "
               "line (sampled.linear true); a row, when every setting placed on it is proved. A row whose setting has "
               "no row of its own but is tied to it (its proof went through it, or its name is the row's) keeps this "
               "status, flagged placement_missing."),
    ("proved or named from a shared list", "Options only, where a proof is read lean (the public form, or a "
                                           "definition read without its evidence): its setting's proof lists the value "
                                           "and says some of the values it lists were named from another setting's "
                                           "proof (proved.shared), never which, so whether this one was chosen on the "
                                           "setting or inferred is not said; the private form, which reads the proof's "
                                           "names, says which (docs/decisions/0025)."),
    ("proved by hand", "A hand-table fact with hand evidence: the owner set it by hand and the kit diffed the camera's "
                       "downloads before and after (a FRAME_PROOFS entry the definition does not carry yet, or a hand "
                       "look that changed records)."),
    ("sampled", "A number scale proved by samples not on one line (sampled.linear null): its values are derived, not "
                "all chosen (privately those its proof names \"sampled\", publicly those it lists). A row, when every "
                "setting placed on it is proved or sampled, one at least sampled."),
    ("not offered", "Options only: a not_offered mark, the camera's menu never offers the value."),
    ("not in the settings file (Sony)", "Sony's Save/Load exclusion list names the row or a row above it (the camera "
                                        "file's save_load_excluded), or the file's header holds it (header_rows); "
                                        "confirmed when a look or a hand check also showed no record differ."),
    ("information screen", "Opening it shows information only: a look saw a screen of a classified read-only kind (a "
                           "notice) whose field names hold one of safety's address field names or a label outside the "
                           "row's path, and no record differ; or its class is a screen of the camera's addresses or its "
                           "serial number. Its field names are kept, never its values. Taken before an action, so an "
                           "information screen the never-open list counts among actions is one."),
    ("action, nothing to map", "The row acts (safety's action class, or a look saw it act) and no setting is placed "
                               "on it."),
    ("tested, no record changes", "Private only: an option was chosen while the row was active, then a camera download "
                                  "was diffed against the run's start: no record but the volatile ones differed. It "
                                  "cites a look or a proof line; a network row's proof that changed nothing never "
                                  "counts (one of them is the saved option chosen again)."),
    ("needs equipment", "Refused for want of named equipment (a lens with a function ring, a power-zoom lens, a shoe "
                        "accessory, a RAW recorder, a flash): a setting's unproved_reason of kind equipment (public), or "
                        "a look's blocker (private only: which equipment the owner had)."),
    ("no proof possible", "Every setting placed on it is proved or carries an unproved_reason, one at least of another "
                          "kind than equipment (state, camera_only, not_on_camera, network, unknown): the reason says "
                          "why no menu choice proves it."),
    ("inferred from a shared list", "Options only, private only, never proved: no proof chose the value on this "
                                    "setting, and the definition's writer named it from another setting's proof (a "
                                    "shared list: a picker's slots, one array's elements, a hold and its live setting, "
                                    "a copy; the whole proof's name source \"derived\", camkit.definitions.inferred, "
                                    "docs/decisions/0025). It takes the place of greyed in state, closed by rule or not "
                                    "yet tried, whose citations the private form keeps beside the setting of its shared "
                                    "list it was proved on, where the ledger's own grouping finds one "
                                    "(kit/tools/coverage.py --shared, which also says where that list's own proof "
                                    "lines do not bear the writer out)."),
    ("greyed in state", "Greyed or refused by a notice. Public only from the definition's inactive_when (inferred: "
                        "inactive_when, the blocker the row it names); privately also from a look line, a crawl row, a "
                        "proof or failure line, or the latest page scan's greyed flag, the blocker the row (and option) "
                        "the notice names, equipment or a remote session open."),
    ("kit cannot read", "Private only: opened or tried, but the kit failed in a way it fails again until the kit "
                        "changes (an unknown screen, no response to Right); the kit's message is kept. A lost row, an "
                        "error or a walk cut short is retried, never this. A kit issue, never a camera fact."),
    ("closed by rule", "camkit.safety.never_open names it, a look lap does not open it (camkit.safety."
                       "look_lap_refused: what OWNER_NEVER names and the Screen Reader, never; a row whose opening acts, "
                       "the owner's own run each time; a format, a delete or a reset, whose first open on a body is the "
                       "owner's own run), and nothing above applies; its class and what opens it today (--network, "
                       "--owner, --allow, an approved motion decision, or never) are kept. Another never-open row is "
                       "not yet tried: a look lap opens it."),
    ("not yet tried", "None of the above."),
)
STATUS_NAMES = tuple(n for n, _ in STATUSES)
RANK = {n: i for i, n in enumerate(STATUS_NAMES)}
# a value the writer named from another setting's proof that no proof chose on its own (camkit.definitions.inferred),
# and the statuses it takes the place of
INFERRED = "inferred from a shared list"
INFERABLE = ("greyed in state", "closed by rule", "not yet tried")
# a value a proof read lean lists, whose setting says some of its listed values were named from another setting's
# proof (proved.shared): proved or inferred, the lean proof does not say which
PROVED_OR_SHARED = "proved or named from a shared list"
# how many values a setting's own record shows as its shared list names them, below which kit/tools/coverage.py
# --shared says the list's own proof lines do not bear the writer's inference out (it decides nothing)
SHARED_OWN = 2
# what settled() counts settled (a run given --skip-settled leaves it out): an answer that holds whatever the camera's
# state, on a row with no value still to try (values_left)
SETTLED = frozenset(("proved", PROVED_OR_SHARED, "proved by hand", "sampled", "not offered",
                     "not in the settings file (Sony)", "information screen", "action, nothing to map",
                     "tested, no record changes", "no proof possible", INFERRED))
# what kit/tools/coverage.py --todo lists, with the next step each needs (and every row with values_left)
TODO = ("needs equipment", "greyed in state", "kit cannot read", "closed by rule", "not yet tried")
# the statuses of a setting's value still to try: values_left counts them on a row, and such a row is never settled
LEFT = ("greyed in state", "kit cannot read", "not yet tried")
# what the public form never holds (public_problems refuses it there): a state seen, a kit's failure, an inference
# from the proof lines (the public build has none)
NEVER_PUBLIC = ("tested, no record changes", "kit cannot read", INFERRED)

RECORD_STATUSES = (
    ("proved", "Every setting on the record is proved (an element no proof can reach, with its unproved_reason, "
               "aside)."),
    ("partly named", "Byte fields of the record are named (key@offset), fewer bytes than the record holds."),
    ("named, no proof possible", "Every setting on it carries an unproved_reason (its kind is kept)."),
    ("named, not proved", "A setting on it has neither a proof nor a reason."),
    ("changed, no row attributed", "Private: no setting covers it, and the camera's downloads were seen to change it "
                                   "(the leads, a proof's diff, a look, pass 2's \"new\", an accepted ruling)."),
    ("unmapped, never seen to change", "Private: no setting covers it, and it held one value in every camera-written "
                                       "download the leads examined."),
    ("unmapped, not examined", "Private: no setting covers it, and nothing examined its variation."),
)
RECORD_NAMES = tuple(n for n, _ in RECORD_STATUSES)
# the public form merges the last three: whether a record varied is the owner's evidence
PUBLIC_RECORD = {"changed, no row attributed": "unmapped", "unmapped, never seen to change": "unmapped",
                 "unmapped, not examined": "unmapped"}
PUBLIC_RECORD_NAMES = RECORD_NAMES[:4] + ("unmapped",)

# ---------------------------------------------------------------- the proof-validity rule

PROOF_VALIDITY = (
    ("a", True, "the diff is the row's own: the records the proof changed, beyond the camera's volatile ones, are all "
                "records of settings placed on the row (or their copies), and there is one at least. The proof that "
                "chooses the saved option again (an attempt's last) changes nothing by design: its value is the start "
                "file's, inferred, so it is never valid (\"inferred\")"),
    ("b", True, "two INDEPENDENT readings recorded in the proof name the option alike, compared whole (camkit.match."
                "same, never a part of one in the other): the OCR reading under the cursor (\"shown\") and the vision "
                "reader's (\"vlm\"), or two OCR engines' votes. pass 1's map label does not count: the prover matched "
                "it itself before choosing. A proof with one reading says so"),
    ("c", True, "across the row (and its context), every option proved writes a different value into the records of "
                "the row's own settings (a side effect on another record never makes two options look distinct), and "
                "as many options are proved as the camera's walked list offers where pass 1's map holds that list"),
    ("d", False, "a round trip: the attempt finished, its last proof (the saved option chosen again) changing nothing"),
)
REQUIRED = tuple(k for k, req, _ in PROOF_VALIDITY if req)

# ---------------------------------------------------------------- the looks file (recorded)

LOOK_BY = ("drive", "crawl", "prove", "hand")
LOOK_DID = ("open", "choose", "act", "lap")
# retract: kit/tools/coverage.py --record --result retract, the latest look of its (row, did, option), says nothing
LOOK_RESULTS = ("no_change", "changed", "refused", "greyed", "kit_failed", "not_reached", "acted", "looked", "retract")
LOOK_KEYS = ("t", "run", "kit", "by", "mode", "tab", "group", "path", "option", "did", "screen", "result", "blocker",
             "fields", "options", "kit_message", "decision", "start_sha256", "end_sha256", "records_changed", "note")
LOOK_REQUIRED = ("t", "by", "path", "did", "result")
BLOCKER_KEYS = ("row", "option", "equipment", "remote")
RECORD_KEY = re.compile(r"^(global|set(\d+)?):0x[0-9a-f]{4}$")
SHA = re.compile(r"^[0-9a-f]{64}$")
# keys the public form never holds, at any depth (kit/tools/check_public.py refuses them there): runs, days, kit
# commits, hashes, frames, citations, what was current or held, values, addresses
PRIVATE_KEYS = frozenset({"t", "run", "runs", "date", "day", "kit", "kit_commit", "commit", "sha256", "start_sha256",
                          "end_sha256", "before", "after", "frame", "frames", "chosen_frame", "row_frame", "dat",
                          "base", "bundle", "bundles", "cites", "cite", "line", "current", "held", "saved", "state",
                          "value", "address", "addresses", "text", "shown", "vlm", "kit_message", "records_changed",
                          "changed_in_looks", "looked", "validity", "proofs", "decision", "by", "note"})
# in any text of the public form: a kit commit or a hash (seven hex digits or more), a date (also one a time follows),
# a run's folder
HEX_RUN = re.compile(r"[0-9a-fA-F]{7,}")
DATE = re.compile(r"\b20\d\d-\d\d-\d\d(?:\b|T)")
RUN_FOLDER = re.compile(r"runs[/\\]")
NEEDS = ("remote-look", "remote-proof", "hand", "equipment", "decision", "kit")
# the equipment a notice or a reason names (safety.NOTICE_EQUIPMENT, beside safety's notice shapes: Sony's wording is a
# camera fact, docs/decisions/0020), and what the public form says where the reason names none of them
EQUIPMENT_NAMES = tuple(dict.fromkeys(n for _, n in safety.NOTICE_EQUIPMENT)) + ("named in its setting's reason",)
REMOTE = "a remote session open"
# the classified screen kinds nothing is chosen on (camkit.screen's notice; "info" for a kind the kit may yet tell):
# only a look at one of them makes an information screen. Never "unknown" (the kit failed to classify it) nor "fields"
# (an editor of number fields)
INFO_KINDS = frozenset({"notice", "info"})
# the kinds whose text a look reads field names from (safety.screen_fields): the information kinds, and the screens a
# private look keeps as field names alone
FIELD_KINDS = INFO_KINDS | {"unknown", "fields"}
# a byte field of a record ("<record>@<offset>": an offset into the record's bytes) is two bytes, little-endian, as the
# editor reads one; the setting's size and count are its record's
FIELD_BYTES = 2
# the kit's failures that come again until the kit changes (camkit.crawl.visit_row's outcomes, a drive look's, a
# prover's): only they make "kit cannot read"; every other failure (lost, error, a walk or a submenu cut short, no label
# read, a run that did not finish or reach the row) is not_reached, tried again by any run
KIT_DETERMINISTIC = re.compile(r"^(unknown screen|no response to right)", re.I)
KIT_TRANSIENT = re.compile(r"^(lost|incomplete|error|submenu: |skipped: no label read)", re.I)
# a crawl row a --skip-settled run left out: its outcome starts so (camkit.crawl writes "skipped: <CrawlGate.skip's>")
CRAWL_SKIPPED = "skipped: settled"


def refused_notice(outcome) -> bool:
    """Whether a crawl row's outcome is a notice that stopped the row (camkit.crawl's "notice", and "notice (named, not
    passed: ...)" where --info-ok named it and it was not passed): greyed; never "notice passed: ...", whose screen
    behind the notice was reached (looked at)."""
    out = str(outcome or "")
    return out.startswith("notice") and not out.startswith("notice passed")


# ---------------------------------------------------------------- where the files are

def looks_dir() -> Path:
    """The folder holding each camera's private ledger files: private/evidence/ (definitions.EVIDENCE_DIR), or
    CAMSET_LOOKS_DIR (the tests point it at a folder of their own, so no test writes the mapper's evidence)."""
    env = os.environ.get("CAMSET_LOOKS_DIR")
    return Path(env) if env else definitions.EVIDENCE_DIR


def looks_file(camera: str) -> Path:
    return looks_dir() / camera / f"looks_{camera}.jsonl"


def private_file(camera: str) -> Path:
    return looks_dir() / camera / f"coverage_{camera}.json"


def leads_file(camera: str) -> Path:
    return looks_dir() / camera / f"leads_{camera}.json"


def public_file(camera: str) -> Path:
    return definitions.data_dir(camera) / f"coverage_{camera}.json"


def seen_file(camera: str, data_dir: Path = None) -> Path:
    """The camera's seen file, data/<model>_fw<fw>/seen_<model>_fw<fw>.json: the allow-listed facts its looks
    established (ALLOWED), the one part of the public form no public source gives (schemas/coverage-seen.schema.json)."""
    return (Path(data_dir) if data_dir is not None else definitions.data_dir(camera)) / f"seen_{camera}.json"


SCHEMA_REF = "../../schemas/coverage.schema.json"
SEEN_SCHEMA_REF = "../../schemas/coverage-seen.schema.json"


# ---------------------------------------------------------------- the kit's commit

_COMMIT = {}


def _git(*args) -> str | None:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() if out.returncode == 0 else None


def _kit_dirty() -> bool | None:
    """Whether kit/ holds changes no commit has (git status --porcelain -- kit, taking no lock on the index), None where
    git cannot tell."""
    out = _git("--no-optional-locks", "status", "--porcelain", "--", "kit")
    return None if out is None else bool(out)


def kit_commit() -> str | None:
    """The kit's commit (git's short hash of HEAD, "+dirty" after it while kit/ holds uncommitted changes, so no later
    run takes the look for one of that commit's), or None where git cannot tell; read once a process."""
    if "head" not in _COMMIT:
        head = _git("rev-parse", "--short=7", "HEAD")
        _COMMIT["head"] = f"{head}+dirty" if head and _kit_dirty() else head
    return _COMMIT["head"]


def kit_newer(than: str | None) -> bool | None:
    """Whether the kit's commit now is newer than `than` (a look's): True when `than` is an ancestor of HEAD and not
    HEAD, False when it is HEAD and kit/ holds no uncommitted change, None when it cannot be told (no commit recorded,
    no git, unrelated commits, a look made on a changed tree, or kit/ changed now: an uncommitted fix may mend it)."""
    if not than or str(than).endswith("+dirty") or _kit_dirty() is not False:
        return None
    head = _git("rev-parse", "HEAD")
    old = _git("rev-parse", f"{than}^{{commit}}")
    if not head or not old:
        return None
    if head == old:
        return False
    try:
        r = subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", old, head], capture_output=True,
                           timeout=10)
    except (OSError, subprocess.SubprocessError):
        return None
    return True if r.returncode == 0 else None


# ---------------------------------------------------------------- writing a look

def now() -> str:
    import datetime
    return datetime.datetime.now().replace(microsecond=0).isoformat()


def look_problems(entry) -> list:
    """Why a look line is not one the looks file holds, in words; [] for one it does (schemas/looks.schema.json says
    the same): its keys LOOK_KEYS, those of LOOK_REQUIRED there, `by`, `did` and `result` of their lists, the path
    labels words, records_changed record keys only and fields words only: never a value."""
    if not isinstance(entry, dict):
        return ["not an object"]
    out = [f"the key {k!r}" for k in entry if k not in LOOK_KEYS]
    out += [f"no {k!r}" for k in LOOK_REQUIRED if k not in entry]
    for k, allowed in (("by", LOOK_BY), ("did", LOOK_DID), ("result", LOOK_RESULTS)):
        if k in entry and entry[k] not in allowed:
            out.append(f"{k} {entry[k]!r} (one of {', '.join(allowed)})")
    if "path" in entry and not (isinstance(entry["path"], list) and all(isinstance(x, str) for x in entry["path"])):
        out.append("path is not a list of labels")
    for k in ("fields", "options"):
        if k in entry and not (isinstance(entry[k], list) and all(isinstance(x, str) for x in entry[k])):
            out.append(f"{k} is not a list of words")
    rc = entry.get("records_changed", [])
    if not (isinstance(rc, list) and all(isinstance(x, str) and RECORD_KEY.match(x) for x in rc)):
        out.append("records_changed holds something other than record keys")
    b = entry.get("blocker")
    if b is not None and not (isinstance(b, dict) and all(k in BLOCKER_KEYS for k in b)):
        out.append("blocker is not {row, option, equipment, remote}")
    for k in ("start_sha256", "end_sha256"):
        if entry.get(k) is not None and not (isinstance(entry[k], str) and SHA.match(entry[k])):
            out.append(f"{k} is not a SHA-256")
    for k in ("t", "run", "kit", "mode", "tab", "group", "option", "screen", "kit_message", "decision", "note"):
        if entry.get(k) is not None and not isinstance(entry[k], str):
            out.append(f"{k} is not words")
    if entry.get("result") == "retract" and (entry.get("records_changed") or entry.get("fields")):
        out.append("a retraction holds no records or fields")
    return out


def append_look(camera: str, entry: dict, private: bool = False, say=None) -> bool:
    """One look added to the camera's looks file (looks_file), never breaking the run that writes it: a line that is
    not one (look_problems) or a write that fails is said in one line and False returned, the run going on with its
    exit status as it was. On a private run (--network, --owner, an address screen) the file and its folder are made
    owner-only (0600, 0700) on POSIX; the line holds what the run itself keeps (safety.kept_screen's field names and
    option names), never a value."""
    say = say or (lambda m: print(m, file=sys.stderr, flush=True))
    try:
        entry = {k: v for k, v in entry.items() if v is not None or k in LOOK_REQUIRED}
        why = look_problems(entry)
        if why:
            say(f"coverage: the look for {' > '.join(entry.get('path') or [])!r} was not recorded ({'; '.join(why[:3])})")
            return False
        p = looks_file(camera)
        p.parent.mkdir(parents=True, exist_ok=True)
        jsonl.append(p, entry)
        if private and os.name != "nt":
            os.chmod(p.parent, 0o700)
            os.chmod(p, 0o600)
        return True
    except Exception as e:          # noqa: BLE001 (a look that cannot be written never stops a run)
        say(f"coverage: the look could not be recorded ({type(e).__name__}: {e}); the run goes on")
        return False


def read_looks(camera: str = None, path: Path = None) -> list:
    """[(line number, look)] of the camera's looks file; [] when there is none. A line that is not a look is left out."""
    p = Path(path) if path is not None else looks_file(camera)
    try:
        lines = jsonl.read(p, bad="skip")
    except (OSError, ValueError):
        return []
    return [(i + 1, x) for i, x in enumerate(lines) if not look_problems(x)]


def latest_looks(looks: list) -> list:
    """[(line, look)] the ledger reads of the looks file: per (row, did, option) the LATEST look alone (the file is in
    the order the looks were made), so a look made since corrects one before it, and a retraction (result "retract")
    leaves nothing; a crawl's lap lines pass through. Rows by their labels compared plain, in any mode."""
    last, laps = _last_looks(looks)
    out = [x for x in last.values() if x[1].get("result") != "retract"] + laps
    return sorted(out, key=lambda x: x[0])


def _last_looks(looks: list) -> tuple:
    """({(row, did, option): (line, look)} the latest look of each, a retraction included, [(line, lap)]). A look that
    did not reach the row (not_reached: an unfinished run, a lost row) never takes the place of an earlier look of the
    same key that did: it says nothing of the row."""
    last, laps = {}, []
    for line, lk in looks:
        if lk.get("did") == "lap":
            laps.append((line, lk))
            continue
        k = (tuple(plain(p) for p in lk.get("path") or []), lk.get("did"), plain(lk.get("option") or ""))
        if lk.get("result") == "not_reached" and k in last and last[k][1].get("result") != "not_reached":
            continue
        last[k] = (line, lk)
    return last, laps


def retracted(looks: list) -> list:
    """[(row labels compared plain, did)] of the looks file's retractions that stand (each the latest of its key)."""
    last, _laps = _last_looks(looks)
    return [(k[0], k[1]) for k, (_line, lk) in last.items() if lk.get("result") == "retract"]


# ---------------------------------------------------------------- the sources

def _read_json(p) -> dict | list | None:
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _fingerprint(p) -> tuple | None:
    try:
        st = Path(p).stat()
        return (st.st_size, st.st_mtime_ns)
    except OSError:
        return None


class Sources:
    """Everything a ledger is generated from (load_sources), each source as read; the private ones empty where the
    computer holds none (a fresh clone, CI, public=True)."""

    def __init__(self, camera: str):
        self.camera = camera
        self.definition = {}
        self.hand = {}
        self.camera_file = {}
        self.help_rows = []
        self.looks = []             # [(line, look)]
        self.crawls = []            # [(run, line, row)] (rows.jsonl)
        self.page_models = {}       # mode -> (run, model)
        self.proofs = []            # [(run, line, proof)]
        self.failures = []          # [(run, line, failure)]
        self.attempts = set()       # finished attempt ids
        self.report_new = set()     # record keys pass 2's report calls "new"
        self.accepted_new = set()
        self.downloads = []         # downloads.jsonl entries
        self.maps = {}              # (path tuple) -> number of options pass 1's map walked
        self.records = {}           # "global:0x...." / "set:0x...." -> (size, count) of the file the records come from
        self.records_from = ""
        self.latest = None          # the latest camera download's path
        self.leads = None
        self.run_root = None
        self.fingerprints = {}
        self.private = False
        self.given = {}             # load_sources' stand-ins (definition, data_dir, records): the public build's too
        self.looks_present = False  # whether the looks file is on this computer (else the seen file's facts alone)
        # the public build's: the allow-listed facts (ALLOWED), the seen file's (read_seen), with the looks' own where
        # the private build has them (public_ledger)
        self.allowed = []


def records_of(path) -> dict:
    """{record key: (size, count)} of a settings file: section 0's as "global:0x....", the memory sets' (one layout)
    as "set:0x...."."""
    from . import camset
    cs = camset.read(path)
    out = {}
    for s, sec in enumerate(cs.sections):
        area = "global" if s == 0 else "set"
        if s > 1:
            continue
        for rid, r in sec.items():
            out[f"{area}:0x{rid:04x}"] = (r.size, r.count)
    return out


def load_sources(camera: str, *, public: bool = False, definition: Path = None, data_dir: Path = None,
                 runs_root: Path = None, looks: Path = None, leads: Path = None, records: dict = None,
                 allowed: list = None) -> Sources:
    """The sources of the camera's ledger. public=True reads the public ones alone (the definition without its
    evidence, data/, safety.py), as a fresh clone has them, with the allow-listed facts `allowed`, else the seen file's
    (read_seen). The paths stand in for the camera's own (a made-up camera in the tests): the definition file, its data
    folder, its runs' folder, its looks file and its leads file; `records` stands in for the file's record ids ({key:
    (size, count)})."""
    src = Sources(camera)
    src.given = {"definition": definition, "data_dir": data_dir, "records": records}
    dpath = Path(definition) if definition is not None else definitions.path(camera)
    src.definition = definitions.load(dpath, evidence=not public) if dpath.exists() else {}
    ddir = Path(data_dir) if data_dir is not None else definitions.data_dir(camera)
    src.hand = _read_json(ddir / f"hand_tables_{camera}.json") or {}
    src.camera_file = _read_json(ddir / f"camera_{camera}.json") or src.definition.get("camera") or {}
    hg = ddir / f"help_guide_menu_{camera}.jsonl"
    try:
        src.help_rows = jsonl.read(hg, bad="skip")
    except (OSError, ValueError):
        src.help_rows = []
    src.fingerprints = {"definition": _fingerprint(dpath), "hand": _fingerprint(ddir / f"hand_tables_{camera}.json"),
                        "camera": _fingerprint(ddir / f"camera_{camera}.json")}
    src.paths = {"definition": dpath, "hand": ddir / f"hand_tables_{camera}.json",
                 "camera": ddir / f"camera_{camera}.json"}
    if records is not None:
        src.records, src.records_from = dict(records), "given"
    if public:
        src.allowed = list(allowed) if allowed is not None else read_seen(camera, ddir)
    else:
        src.private = True
        lpath = Path(looks) if looks is not None else looks_file(camera)
        src.looks_present = lpath.exists()
        src.looks = read_looks(path=lpath)
        root = Path(runs_root) if runs_root is not None else paths.runs_top() / camera
        src.run_root = root
        if root.is_dir():
            _load_runs(src, root)
        accepted = _read_json(looks_dir() / camera / f"accepted_{camera}.json") \
            if looks is None else _read_json(Path(looks).parent / f"accepted_{camera}.json")
        src.accepted_new = _new_keys(accepted, accepted=True)
        lp = Path(leads) if leads is not None else (leads_file(camera) if looks is None
                                                     else Path(looks).parent / f"leads_{camera}.json")
        src.leads = _read_json(lp) if lp.exists() else None
    if not src.records:
        sample = definitions.sample(src.definition, dpath) if src.definition else None
        for p, what in ((src.latest, "the latest download"), (sample, "the definition's sample")):
            if p is not None and Path(p).exists():
                try:
                    src.records, src.records_from = records_of(p), what
                    break
                except (OSError, ValueError):
                    continue
    return src


def _new_keys(doc, accepted: bool = False) -> set:
    """The record keys a report (or the accepted rulings) calls "new" (seen to change, no setting), found wherever
    they sit in the file: {"records": {key: {"verdict": "new"}}}, or an accepted entry {"kind": "new", "key"}."""
    out = set()

    def walk(x):
        if isinstance(x, dict):
            if accepted and x.get("kind") == "new" and isinstance(x.get("key"), str):
                out.add(x["key"])
            recs = x.get("records")
            if isinstance(recs, dict):
                for k, v in recs.items():
                    if isinstance(v, dict) and v.get("verdict") == "new":
                        out.add(k)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(doc)
    return {record_base(k) for k in out if record_base(k)}


def _jsonl(p) -> list:
    try:
        return jsonl.read(p, bad="skip")
    except (OSError, ValueError):
        return []


def _recorded_mode(scan) -> str | None:
    """The shooting mode a page scan recorded (runner.recorded_mode, as runner.SCAN_MODES spell it), None for none."""
    try:
        import runner
        return runner.recorded_mode(scan)
    except (Exception, SystemExit):     # noqa: BLE001 (kit/ not importable here: the scan names no mode)
        return None


def _load_runs(src: Sources, root: Path) -> None:
    """The run folders' logs (rows.jsonl, proofs.jsonl, failures.jsonl, attempts.jsonl), the latest page model of each
    mode, pass 2's report, pass 1's map, the downloads manifest and the latest download."""
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        for i, r in enumerate(_jsonl(d / "rows.jsonl")):
            src.crawls.append((d.name, i + 1, r))
        for i, r in enumerate(_jsonl(d / "proofs.jsonl")):
            src.proofs.append((d.name, i + 1, r))
        for i, r in enumerate(_jsonl(d / "failures.jsonl")):
            src.failures.append((d.name, i + 1, r))
        src.attempts |= {x.get("attempt") for x in _jsonl(d / "attempts.jsonl") if x.get("complete")}
        model = d / "model.json"
        if model.exists():
            mode = _recorded_mode(d)
            if mode:
                have = src.page_models.get(mode)
                stamp = model.stat().st_mtime_ns
                if have is None or stamp > have[2]:
                    doc = _read_json(model)
                    if isinstance(doc, list):
                        src.page_models[mode] = (d.name, doc, stamp)
        if (d / "report.json").exists() and d.name.endswith("pass2"):
            src.report_new |= _new_keys(_read_json(d / "report.json"))
        if (d / "map_all.json").exists():
            for r in (_read_json(d / "map_all.json") or {}).get("rows") or []:
                if isinstance(r, dict) and isinstance(r.get("path"), list):
                    n = len({json.dumps(o.get("index")) for o in r.get("options") or [] if isinstance(o, dict)})   # a panel's index is a list
                    if n and r.get("wrapped", True) is not False:
                        src.maps[tuple(r["path"])] = n
    src.downloads = _jsonl(root / "downloads.jsonl")
    for e in reversed(src.downloads):
        p = root / str(e.get("path", ""))
        if p.exists():
            src.latest = p
            break


# ---------------------------------------------------------------- keys and labels

def record_base(key) -> str | None:
    """A setting's or a change's key as its record's: "global:0x05af[6]" and "global:0x018c@45" give "global:0x05af"
    and "global:0x018c"; "set3:0x0180" gives "set:0x0180"."""
    m = re.match(r"^(global|set)\d*:(0x[0-9a-f]{4})", str(key or ""))
    return f"{m.group(1)}:{m.group(2)}" if m else None


# the labels' folds and comparisons memoised while a build runs (build: {function: {arguments: result}}, else None):
# a build folds the same labels about a million times (1,641 distinct strings and 65,920 pairs on the a1 II,
# 2026-11-18), and the folds themselves (camkit.safety, camkit.match) stay uncached, as the guards use them
_MEMO = None


def _memo(fn, *args):
    """fn(*args), from this build's memo when it is there (_MEMO): `fn` is a pure fold or comparison of labels."""
    if _MEMO is None:
        return fn(*args)
    table = _MEMO.setdefault(fn, {})
    try:
        return table[args]
    except KeyError:
        got = table[args] = fn(*args)
        return got
    except TypeError:                   # an argument that cannot be a key: not memoised
        return fn(*args)


def _same(a, b) -> bool:
    """camkit.match.same(a, b), memoised for the build (_memo)."""
    return _memo(match.same, a, b)


def plain(text) -> str:
    """A label as the ledger compares it: safety.plain's (folded, the signs an icon reads as left out, case and spacing
    aside), and "" for none."""
    return _memo(safety.plain, str(text or ""))


def same_label(a, b) -> bool:
    """Two labels of one row: camkit.match.same's (an OCR slip aside, digits and short words exact), or one the other
    cut short ("Face Priority in Mul...", a page model's), which match.same does not take."""
    return _memo(_same_label, a, b)


def _same_label(a, b) -> bool:
    x, y = plain(a), plain(b)
    if not x or not y:
        return False
    # match.same takes no pair this far apart in length (its ratio of 0.85 needs three quarters): asked of the others
    if x == y or (min(len(x), len(y)) >= 0.7 * max(len(x), len(y)) and _same(a, b)):
        return True
    x, y = (" ".join(str(t or "").casefold().split()) for t in (a, b))
    return any(p.endswith("...") and len(p) > 3 and q.startswith(p[:-3]) for p, q in ((x, y), (y, x)))


def setting_state(s: dict) -> str | None:
    """A setting's own status: proved, sampled (a scale off its line), needs equipment, no proof possible, or None
    (named, not proved)."""
    p = s.get("proved")
    if isinstance(p, dict):
        if "sampled" in p and (p.get("sampled") or {}).get("linear") is not True:
            return "sampled"
        return "proved"
    r = s.get("unproved_reason")
    if isinstance(r, dict):
        return "needs equipment" if r.get("kind") == "equipment" else "no proof possible"
    return None


def rule_class(label: str) -> str | None:
    """The class of camkit.safety's never-open list a row's label is of, in the words the ledger keeps, or None (the
    row is open): action, card action, credentials, identity/by hand, sound/light (by hand), motion, network setting,
    address screen."""
    why = safety.never_open(label)
    if not why:
        return None
    if why.startswith("action:"):
        return "card action" if re.search(r"\b(format|delete)\b", label, re.I) else "action"
    if why.startswith("credentials:"):
        return "credentials"
    if why.startswith("by hand only:"):
        return "identity/by hand" if safety.identity_row(label) else "sound/light (by hand)"
    if why.startswith(safety.MOTION):
        return "motion"
    return "address screen" if safety.address_screen(label) else "network setting"


def openers(label: str) -> list:
    """What opens a never-open row under today's code: --network (a look lap, docs/decisions/0024: every row
    safety.look_lap_refused lets open on a body with no records, so never a format, a delete or a reset, whose first open
    is the owner's own run; or a dated network decision: safety.lift_class), --owner (a dated owner decision,
    kit/drive.py: safety.owner_class), --allow (a run's own allowance: safety.allow_refused), motion (an approved_rows
    decision: safety.owner_may_approve), or never."""
    why = safety.never_open(label)
    if not why:
        return []
    out = []
    if safety.lift_class(label) or not safety.look_lap_refused(label, False):
        out.append("--network")
    if safety.owner_class(label):
        out.append("--owner")
    if not safety.allow_refused(label):
        out.append("--allow")
    if safety.owner_may_approve(why):
        out.append("motion")
    return out or ["never"]


def kit_words(message) -> str | None:
    """The kit's own message as the ledger keeps it: its quoted texts withheld (safety.quoted_withheld: a quote can be
    an option read off the screen, the camera's state), at most 200 characters; None for none."""
    if not message:
        return None
    return safety.quoted_withheld(str(message))[:200]


def equipment_in(text) -> str | None:
    """The equipment a notice's or a reason's words want (safety.NOTICE_EQUIPMENT), or None."""
    for rx, what in safety.NOTICE_EQUIPMENT:
        if rx.search(str(text or "")):
            return what
    return None


def excluded_under(path: tuple, sony: dict, header: set) -> tuple | None:
    """The row of Sony's Save/Load list (or of the file's header) that a row's path is, or is below, the nearest one,
    as the list writes it; None for none: a row below a row the list leaves out of the settings file is left out with
    it. Compared folded (plain), as the ledger compares labels everywhere else: "FTP Transfer Func" is the list's
    "FTP Transfer Func." (review B11, 2026-11-18)."""
    folded = {}
    for k in (*header, *sony):          # the list's own spelling where both name the row
        folded[tuple(plain(x) for x in k)] = k
    for n in range(len(path), 0, -1):
        k = folded.get(tuple(plain(x) for x in path[:n]))
        if k is not None:
            return k
    return None


def save_load(camera_file: dict) -> tuple:
    """({row path tuple: note or ""} Sony's Save/Load list names, {row path tuple} the header holds) from the camera
    file's save_load_excluded."""
    x = camera_file.get("save_load_excluded") or {}
    rows = {}
    for e in x.get("rows") or []:
        if isinstance(e, dict) and isinstance(e.get("row"), str):
            rows[tuple(p.strip() for p in e["row"].split(" > "))] = e.get("note") or ""
    header = {tuple(p.strip() for p in str(r).split(" > ")) for r in x.get("header_rows") or []}
    return rows, header


# ---------------------------------------------------------------- the ledger

class Ledger:
    """The generated ledger: rows (top-level and deeper), options (per setting, value -> status) and records, each
    entry with one status; facts kept for the private form (cites, kit messages, validity) beside it."""

    def __init__(self, src: Sources):
        self.src = src
        self.camera = src.camera
        self.rows = []
        self.options = []
        self.records = []
        self.unresolved = []        # looks no entry could be found for
        self.proof_summary = {}
        self.bundles = []
        self.option_validity = {}   # (setting key, value) -> "valid" or "unchecked (<conditions missing>)"

    def stale(self) -> bool:
        """Whether a source the ledger was generated from changed since (the definition, the hand tables, the camera
        file): a stale ledger skips nothing."""
        return any(_fingerprint(p) != self.src.fingerprints.get(k) for k, p in self.src.paths.items())

    def find(self, path, mode=None, tab=None, group=None) -> list:
        """The row entries a path names: by its labels (same_label), in that mode, tab and group where given."""
        path = [str(x) for x in path or []]
        if getattr(self, "_by_path", None) is None or self._indexed != len(self.rows):
            self._by_path, self._indexed = {}, len(self.rows)
            for e in self.rows:
                self._by_path.setdefault(tuple(plain(p) for p in e["path"]), []).append(e)
        key = tuple(plain(p) for p in path)
        cands = self._by_path.get(key)
        if cands is None:               # a slip or a label cut short ("Face Priority in Mul..."): judged one by one, once
            memo = self.__dict__.setdefault("_judged", {})
            if (key, self._indexed) not in memo:
                memo[(key, self._indexed)] = [e for e in self.rows if len(e["path"]) == len(path)
                                              and all(same_label(a, b) for a, b in zip(e["path"], path, strict=True))]
            cands = memo[(key, self._indexed)]
        out = []
        for e in cands:
            if mode and e["mode"] != mode:
                continue
            if tab and plain(e["tab"]) != plain(tab):
                continue
            if group and plain(e["group"]) != plain(group):
                continue
            out.append(e)
        return out


def _order(defn: dict) -> dict:
    return {t: i for i, t in enumerate(list(defn.get("tabs") or []) + ["My Menu"])}


def build(camera: str = None, *, src: Sources = None, public: bool = False, validity: bool = False) -> Ledger:
    """The camera's ledger, generated from its sources (load_sources; `src` given as made). validity: the proofs'
    validity and evidence bundles too (the private form; kit/tools/coverage.py). The labels' folds are memoised for
    the length of the build (_MEMO), a build inside it (public_ledger's) sharing them."""
    global _MEMO
    outer = _MEMO
    _MEMO = {} if outer is None else outer
    try:
        return _build(camera, src, public, validity)
    finally:
        _MEMO = outer


def _build(camera, src, public, validity) -> Ledger:
    src = src or load_sources(camera, public=public)
    led = Ledger(src)
    defn = src.definition
    if not defn:
        return led
    settings = defn.get("settings") or []
    by_key = {s["key"]: s for s in settings}
    _universe(led, defn, settings, src)
    facts = _facts(led, src, by_key)
    _row_statuses(led, facts, by_key, src)
    _option_statuses(led, settings, facts, src)
    _cite_shared(led)
    _values_left(led)
    _record_statuses(led, settings, src, facts)
    if validity:
        _validity(led, by_key, src)
    return led


def public_ledger(led: Ledger) -> Ledger:
    """The ledger the public form is written from: `led` itself where it was built from the public sources alone (with
    the seen file's facts), else one built again from them (the private build's own stand-ins: its definition file,
    data folder and record ids) with the facts public_seen gives: the seen file's, and where the looks file is on this
    computer its own allow-listed facts too, its retractions taking committed ones out. Nothing the private sources
    hold reaches it otherwise: no crawl, scan, proof, failure, download, lead or look beyond the allow-list."""
    if not led.src.private:
        return led
    if getattr(led, "_public", None) is None:
        g = led.src.given

        def public(allowed):
            return build(src=load_sources(led.camera, public=True, definition=g.get("definition"),
                                          data_dir=g.get("data_dir"), records=g.get("records"), allowed=allowed))
        facts = read_seen(led.camera, g.get("data_dir"))
        if led.src.looks_present:
            local = allowed_from_looks(led.src.looks, load_sources(led.camera, public=True,
                                                                   definition=g.get("definition"),
                                                                   data_dir=g.get("data_dir"), allowed=[]))
            facts = merged_facts(facts, local, retracted(led.src.looks))
        led._seen = normalized_facts(facts, public(facts))
        led._public = public(led._seen)
    return led._public


def public_seen(led: Ledger) -> list:
    """The seen file's facts the public form is written with (normalized_facts): public_ledger's."""
    if not led.src.private:
        return normalized_facts(led.src.allowed, led)
    public_ledger(led)
    return led._seen


def public_build(camera: str, data_dir: Path = None, definition: Path = None) -> Ledger:
    """The public build check_public and --check compare the committed form with: the camera's public sources and its
    seen file alone (`data_dir`: the folder they are in, else the camera's own; `definition`: its definition file,
    else the camera's own), no looks, no runs."""
    return build(src=load_sources(camera, public=True, data_dir=data_dir, definition=definition))


def _entry(mode, tab, group, path, source, order, nth=0) -> dict:
    return {"mode": mode, "tab": tab, "group": group, "path": list(path), "nth": nth, "source": source,
            "order": order, "settings": [], "tied": [], "through": [], "status": None}


def _universe(led: Ledger, defn: dict, settings: list, src: Sources) -> None:
    """The rows: the definition's menu (MENU_MODE), the rows only another mode's menu has (a setting's row_mode), the
    Help Guide's rows no scan has seen (a tab the menu lacks, or another mode's), and every deeper row a setting's row
    path, a look or a crawl names below a top row."""
    tabs = _order(defn)
    tops, seen = [], {}
    for i, m in enumerate(defn.get("menu") or []):
        k = (MENU_MODE, m["tab"], plain(m["label"]))
        nth = seen.get(k, 0)
        seen[k] = nth + 1
        tops.append(_entry(MENU_MODE, m["tab"], m["group"], [m["label"]], "menu", (tabs.get(m["tab"], 99), 0, i), nth))
    menu_tabs = {m["tab"] for m in defn.get("menu") or []}
    known = {(e["tab"], plain(e["path"][0])) for e in tops}
    extra = {}
    for s in settings:
        row, mode = s.get("row"), s.get("row_mode")
        if not row or not mode or mode == MENU_MODE:
            continue
        tab = s.get("row_tab") or s["tab"]
        if (tab, plain(row[0])) in known:
            continue
        extra.setdefault((mode, tab, plain(row[0])), (mode, tab, s.get("row_group") or s["group"], row[0]))
    for k in sorted(extra, key=lambda k: (tabs.get(k[1], 99), extra[k][2], k[2])):
        mode, tab, group, label = extra[k]
        tops.append(_entry(mode, tab, group, [label], "mode", (tabs.get(tab, 99), 1, len(tops))))
        known.add((tab, plain(label)))
    for i, h in enumerate(src.help_rows):
        modes, tab = str(h.get("modes") or ""), h.get("tab")
        item = str(h.get("item") or "").split(": ")[0].strip()
        if not modes or not tab or not item:
            continue
        mode = MENU_MODE if "still image" in modes else OTHER_MODE
        if mode == MENU_MODE and tab in menu_tabs:
            continue                # the scan has seen that tab in that mode: a row it lacks is not on this body's menu
        if any(e["tab"] == tab and same_label(e["path"][0], item) for e in tops):
            continue
        tops.append(_entry(mode, tab, h.get("group") or "", [item], "help guide", (tabs.get(tab, 99), 2, i)))
    led.rows = tops
    # each placed setting onto its top row (row_mode's, else the menu's), then its deeper rows
    index = {}
    for e in tops:
        index.setdefault((e["mode"], e["tab"], plain(e["path"][0])), e)
    subs = {}
    for s in settings:
        row = s.get("row")
        if not row:
            continue
        tab = s.get("row_tab") or s["tab"]
        top = (index.get((s.get("row_mode") or MENU_MODE, tab, plain(row[0])))
               or index.get((MENU_MODE, tab, plain(row[0])))
               or next((e for k, e in index.items() if k[1] == tab and k[2] == plain(row[0])), None))
        if top is None:
            top = _entry(s.get("row_mode") or MENU_MODE, tab, s.get("row_group") or s["group"], [row[0]], "setting",
                         (tabs.get(tab, 99), 3, len(led.rows)))
            led.rows.append(top)
            index[(top["mode"], tab, plain(row[0]))] = top
        top["settings"].append(s["key"])
        for k in range(2, len(row) + 1):
            key = (id(top), tuple(plain(x) for x in row[:k]))
            if key not in subs:
                subs[key] = _entry(top["mode"], top["tab"], top["group"], row[:k], "setting", top["order"])
                subs[key]["top"] = top
            subs[key]["settings"].append(s["key"])
    # a deeper row a look or a crawl names by a label that reads as a row a setting is placed on, under the same row
    # above (same_label: a slip or a cut, "Operation in Vertical Orientati"; an icon read as letters, "S&Q Record
    # Setting"), is that row: no entry of its own, and Ledger.find takes its facts there
    placed = {}
    for (top_id, labels), e in subs.items():
        placed.setdefault((top_id, labels[:-1]), []).append(e)
    # the deeper rows a look or a crawl names (a submenu's rows holding no setting)
    for path, mode, tab in _seen_paths(src, led):
        top = index.get((mode or MENU_MODE, tab, plain(path[0]))) if tab else None
        if top is None:
            cands = [e for e in tops if same_label(e["path"][0], path[0]) and (not mode or e["mode"] == mode)]
            top = cands[0] if len(cands) == 1 else None
        if top is None:
            continue
        for k in range(2, len(path) + 1):
            key = (id(top), tuple(plain(x) for x in path[:k]))
            if key not in subs:
                if any(same_label(e["path"][-1], path[k - 1]) for e in placed.get((id(top), key[1][:-1]), [])):
                    break
                subs[key] = _entry(top["mode"], top["tab"], top["group"], [top["path"][0], *path[1:k]], "look",
                                   top["order"])
                subs[key]["top"] = top
    # top rows in order, each followed by its deeper rows by path
    ordered = []
    by_top = {}
    for e in subs.values():
        by_top.setdefault(id(e["top"]), []).append(e)
    for e in sorted(led.rows, key=lambda e: e["order"]):
        ordered.append(e)
        ordered += sorted(by_top.get(id(e), []), key=lambda x: [plain(p) for p in x["path"]])
    for e in subs.values():
        e.pop("top", None)
    led.rows = ordered


def _seen_paths(src: Sources, led: Ledger) -> list:
    """(path, mode, tab) of the rows deeper than a top row the private sources name (looks and crawl submenus), or in
    the public build the allow-listed facts alone."""
    if not src.private:
        return [(x["path"], x.get("mode"), x.get("tab")) for x in src.allowed
                if len(x.get("path") or []) > 1 and all(isinstance(p, str) and p for p in x["path"])]
    out = []
    for _, lk in src.looks:
        if len(lk.get("path") or []) > 1:
            out.append((lk["path"], lk.get("mode"), lk.get("tab")))
    crumbs = _crumbs(src)
    for _run, _line, r in src.crawls:
        tab = (crumbs.get(r.get("page")) or [None])[0]
        for sub in r.get("submenu") or []:
            if isinstance(sub, dict) and sub.get("label"):
                out.append(([r.get("decided") or r.get("label") or "", sub["label"]], None, tab))
    return [(p, m, t) for p, m, t in out if all(isinstance(x, str) and x for x in p) and not named_placeholder(src, p)]


def placeholder_label(label) -> bool:
    """A label a look lap or a --network walk kept no name for (kit/crawl_run.py's WITHHELD_LABEL, "(withheld)";
    camkit.first_open.placeholder): no row the kit knows, docs/decisions/0024."""
    return str(label or "").startswith("(")


def named_placeholder(src: Sources, path) -> bool:
    """Whether a path holds a placeholder that the crawls name: under the row before its first placeholder, every
    position a crawl's submenu holds a placeholder at is, in another crawl of that row, a known label (a submenu of the
    same length): one of the rows the kit knows by name, so the placeholder is no row of its own. A placeholder no crawl
    names, or one under a row no crawl walked with it, stays a row (and so in view)."""
    cut = next((i for i, x in enumerate(path or []) if placeholder_label(x)), None)
    if not cut:
        return False
    if getattr(src, "_named_ph", None) is None:
        lists = {}

        def walk(node, parent):
            label = node.get("decided") or node.get("label") or ""
            path_ = (*parent, plain(label))
            subs = [s for s in node.get("submenu") or [] if isinstance(s, dict)]
            if subs and label and not placeholder_label(label):
                lists.setdefault(path_, []).append([s.get("decided") or s.get("label") or "" for s in subs])
            for s in subs:
                walk(s, path_)
        for _run, _line, r in src.crawls:
            walk(r, ())
        named = set()
        for key, ls in lists.items():
            spots = {(len(ls_), i) for ls_ in ls for i, x in enumerate(ls_) if placeholder_label(x)}
            known = {(len(ls_), i) for ls_ in ls for i, x in enumerate(ls_) if x and not placeholder_label(x)}
            if spots and spots <= known:
                named.add(key)
        src._named_ph = named
    return tuple(plain(x) for x in path[:cut]) in src._named_ph


def _crumbs(src: Sources) -> dict:
    """{page key: [tab, group]} of every page model on this computer (a crawl row names its page by key)."""
    if getattr(src, "_crumbs", None) is not None:
        return src._crumbs
    out = {}
    root = src.run_root
    if root is not None and root.is_dir():
        for d in sorted(root.glob("*/model.json")):
            for p in _read_json(d) or []:
                if isinstance(p, dict) and p.get("breadcrumb"):
                    crumb = [x.strip() for x in str(p["breadcrumb"]).split(" > ")][:2]
                    for k in (p.get("key"), p.get("page")):         # a crawl row names its page by its counter
                        if k:
                            out.setdefault(k, crumb)
    src._crumbs = out
    return out


# ---------------------------------------------------------------- facts: the private sources, and the allow-list

class Facts:
    def __init__(self):
        self.by_row = {}            # id(entry) -> {kind: [fact]}
        self.by_option = {}         # (setting key, value) -> {kind: [fact]}
        self.changed_records = {}   # record key -> [cite]

    def row(self, e, kind, fact):
        self.by_row.setdefault(id(e), {}).setdefault(kind, []).append(fact)

    def option(self, key, value, kind, fact):
        self.by_option.setdefault((key, value), {}).setdefault(kind, []).append(fact)

    def of(self, e) -> dict:
        return self.by_row.get(id(e), {})


def known_labels(defn: dict, help_rows=(), camera_file: dict = None) -> set:
    """Every row label the public sources know, as they write it: the definition's menu, its settings' row labels and
    names and the rows their inactive_when names; each part of a Help Guide item ("Image Quality Settings: File
    Format"); the rows of the maker's Save/Load list (the camera file's save_load_excluded)."""
    out = {m["label"] for m in defn.get("menu") or []}
    for s in defn.get("settings") or []:
        out |= set(s.get("row") or [])
        out.add(s.get("name") or "")
        if isinstance(s.get("inactive_when"), dict):
            out.add(s["inactive_when"].get("name") or "")
    for h in help_rows or ():
        out |= {p.strip() for p in str(h.get("item") or "").split(": ")}
    for row in save_load(camera_file or {})[0]:
        out |= set(row)
    return {x for x in out if isinstance(x, str) and x}


class Vocab:
    """The words a public form and its seen file may hold (public_problems' closed vocabulary), from the public sources
    alone: row labels (known_labels), groups and tabs of the definition and the Help Guide's list, field names (the kit's
    address field names, safety.ADDRESS_FIELDS, alone), the equipment (EQUIPMENT_NAMES), the notes of the maker's
    Save/Load list, the unproved_reason kinds, each setting's value codes. label(), group() and tab() give a word as the
    sources write it, None for one they do not know."""

    def __init__(self, defn: dict, help_rows=(), camera_file: dict = None):
        defn = defn or {}
        self.label_set = known_labels(defn, help_rows, camera_file)
        self.labels = {plain(x): x for x in sorted(self.label_set)}
        groups = {m.get("group") for m in defn.get("menu") or []}
        groups |= {s.get(k) for s in defn.get("settings") or [] for k in ("group", "row_group")}
        groups |= {h.get("group") for h in help_rows or ()}
        self.group_set = {g for g in groups if isinstance(g, str)}
        tabs = set(defn.get("tabs") or []) | {"My Menu"} | {m.get("tab") for m in defn.get("menu") or []}
        tabs |= {s.get(k) for s in defn.get("settings") or [] for k in ("tab", "row_tab")}
        tabs |= {h.get("tab") for h in help_rows or ()}
        self.tab_set = {t for t in tabs if isinstance(t, str) and t}
        self.fields = set(safety.ADDRESS_FIELDS)
        self.notes = {n for n in save_load(camera_file or {})[0].values() if n}
        self.kinds = {(s.get("unproved_reason") or {}).get("kind") for s in defn.get("settings") or []
                      if isinstance(s.get("unproved_reason"), dict)} - {None}
        self.values = {s["key"]: {v for v, _ in s.get("values") or []} for s in defn.get("settings") or []}

    def label(self, x) -> str | None:
        return self.labels.get(plain(x)) if isinstance(x, str) else None

    def group(self, x) -> str | None:
        return x if x in self.group_set else None

    def tab(self, x) -> str | None:
        return x if x in self.tab_set else None


def vocab_of(src: Sources) -> Vocab:
    if getattr(src, "_vocab", None) is None:
        src._vocab = Vocab(src.definition, src.help_rows, src.camera_file)
    return src._vocab


def blocker_of(text, labels) -> dict | None:
    """A blocker as a rule from a notice's or a failure's words: first the row label the kit knows that they name after
    "as follows" (or whole), never the value after it ("... as follows Flash Mode Flash Off" is Flash Mode, "Release
    w/o Lens Disable" Release w/o Lens); else the equipment they ask for (safety.NOTICE_EQUIPMENT); else a remote
    session when they say one is open (safety.NOTICE_REMOTE)."""
    t = " ".join(str(text or "").split())
    if not t:
        return None
    tail = t.split("as follows", 1)[-1].strip(" .:") if "as follows" in t else t
    label = safety.blocker_known(tail, labels) or next(
        (x for x in sorted(labels, key=lambda x: (-len(x), x)) if plain(tail).startswith(plain(x) + " ") or
         plain(tail) == plain(x)), None)
    if label:
        return {"row": label}
    eq = equipment_in(t)
    if eq:
        return {"equipment": eq}
    return {"remote": REMOTE} if safety.NOTICE_REMOTE.search(t) else None


def info_fields(lk: dict, vocab: Vocab, public: bool = False) -> list:
    """The field names that make a look one of an information screen, or [] for a look that is none: a look that opened
    the row (did "open") and changed nothing, on a screen of a classified read-only kind (INFO_KINDS: never "unknown",
    never "fields"), whose fields hold one of the kit's address field names (safety.ADDRESS_FIELDS) or a row label
    outside the row's own path. Privately those names and the labels the sources know are given; public=True gives the
    address field names alone, and nothing where there is none: a row label (another row's, a list's, what the screen
    showed in that state) qualifies a look privately only."""
    if lk.get("did") != "open" or lk.get("result") != "no_change" or lk.get("screen") not in INFO_KINDS:
        return []
    own = {plain(p) for p in lk.get("path") or []}
    named = [x for x in lk.get("fields") or [] if isinstance(x, str)]
    if not any(x in safety.ADDRESS_FIELDS or (vocab.label(x) and plain(x) not in own) for x in named):
        return []
    if public:
        return list(dict.fromkeys(x for x in named if x in safety.ADDRESS_FIELDS))
    return list(dict.fromkeys(x if x in safety.ADDRESS_FIELDS else vocab.label(x) for x in named
                              if x in safety.ADDRESS_FIELDS or vocab.label(x)))


def _volatile(src: Sources) -> set:
    return {f"global:0x{r:04x}" for r in (src.camera_file.get("volatile_records") or [])}


# the facts a look establishes that the public form may hold, true of every camera of the model (docs/decisions/0016),
# as the seen file names them: an information screen and its address field names, a row acting when opened, a hand
# check that changed a record, a row on the maker's Save/Load list seen to change nothing; and the facts of the ledger
# each one gives
ALLOWED = ("info", "acted", "hand_changed", "confirmed")
FACT_OF = {"info": "info", "acted": "acted", "hand_changed": "hand_changed", "confirmed": "no_change_any"}
# the facts a retraction of a look takes out of the seen file, by what the look did
RETRACTS = {"open": ("info", "acted", "confirmed"), "choose": ("hand_changed", "confirmed"), "act": ("acted",)}
MODES = ("Stills", "Movie", "S&Q")
SEEN_ABOUT = ("The facts this camera's looks established that its coverage ledger's public form carries, the one part "
              "of it no public source gives, written by kit/tools/coverage.py --write where the mapper's looks file is "
              "(docs/decisions/0023): rows that open an information screen with the kit's address field names, rows "
              "that act when opened, rows and values a hand check saw change a record, rows of the maker's Save/Load "
              "list seen to change nothing. Each holds true of every camera of the model: never a run, a date, a "
              "state seen or a value (docs/decisions/0016).")


def read_seen(camera: str, data_dir: Path = None) -> list:
    """The facts of the camera's seen file (seen_file), [] where there is none or it cannot be read."""
    doc = _read_json(seen_file(camera, data_dir))
    facts = doc.get("facts") if isinstance(doc, dict) else None
    return [x for x in facts or [] if isinstance(x, dict)]


def allowed_from_looks(looks: list, src: Sources) -> list:
    """The allow-listed facts (ALLOWED) of the looks (the latest per row, did and option: latest_looks), each with the
    row's path as the public sources write it (a look naming a label they do not know gives none), its mode, tab and
    group where they know them, an information screen's address field names (info_fields, public) and a hand check's
    option label (which only finds the values it names, written as their codes: normalized_facts): nothing else."""
    v = vocab_of(src)
    volatile = _volatile(src)
    sony, header = save_load(src.camera_file)
    out = []
    for _line, lk in latest_looks(looks):
        if lk.get("did") == "lap":
            continue
        path = [v.label(p) for p in lk.get("path") or []]
        if not path or None in path:
            continue
        place = {"path": path, "mode": lk.get("mode") if lk.get("mode") in MODES else None,
                 "tab": v.tab(lk.get("tab")), "group": v.group(lk.get("group"))}
        res = lk.get("result")
        changed = [k for k in lk.get("records_changed") or [] if record_base(k) not in volatile]
        fields = info_fields(lk, v, public=True)
        if fields:
            out.append({"kind": "info", **place, "fields": fields})
        elif res == "acted":
            out.append({"kind": "acted", **place})
        elif lk.get("by") == "hand" and (res == "changed" or changed):
            out.append({"kind": "hand_changed", **place,
                        **({"option": lk["option"]} if isinstance(lk.get("option"), str) else {})})
        if res == "no_change" and (tuple(path) in sony or tuple(path) in header):
            out.append({"kind": "confirmed", **place})
    return out


def merged_facts(committed: list, local: list, gone: list) -> list:
    """The seen file's facts (`committed`) with the local looks' own (`local`), so a computer whose looks file lacks
    some committed fact keeps it; a local retraction (`gone`: retracted's (row, did)) takes out the committed facts of
    that row the look's kind gives (RETRACTS)."""
    def taken(x):
        row = tuple(plain(p) for p in x.get("path") or [])
        return any(row == r and x.get("kind") in RETRACTS.get(did, ()) for r, did in gone)
    return [x for x in committed if not taken(x)] + list(local)


def _fact_entry(led: Ledger, x: dict) -> dict | None:
    path = x.get("path") or []
    es = led.find(path, x.get("mode"), x.get("tab"), x.get("group")) or led.find(path, None, x.get("tab")) \
        or led.find(path)
    es = [e for e in es if e["nth"] == (x.get("nth") or 0)] or es
    return es[0] if es else None


def normalized_facts(facts: list, led: Ledger) -> list:
    """The seen file's facts as it is written: each on the row of `led` it names (one it names none of is left out),
    with that row's mode, tab, group, path (and nth), an information screen's address field names, a hand check's
    values as {setting key: [value codes]} (its option label read through the row's settings, never written); one fact
    per kind and row (fields and values merged), in the ledger's row order."""
    v = vocab_of(led.src)
    by_key = {s["key"]: s for s in led.src.definition.get("settings") or []}
    order = {id(e): i for i, e in enumerate(led.rows)}
    out = {}
    for x in facts:
        kind = x.get("kind")
        e = _fact_entry(led, x) if kind in ALLOWED else None
        if e is None:
            continue
        k = (order[id(e)], ALLOWED.index(kind))
        f = out.setdefault(k, {"kind": kind, "mode": e["mode"], "tab": e["tab"], "group": e["group"],
                               "path": list(e["path"]), **({"nth": e["nth"]} if e["nth"] else {})})
        if kind == "info":
            f["fields"] = list(dict.fromkeys(f.get("fields", []) + [y for y in x.get("fields") or []
                                                                    if y in safety.ADDRESS_FIELDS]))
        if kind == "hand_changed":
            named = [(key, code) for key, codes in (x.get("values") or {}).items() if isinstance(codes, list)
                     for code in codes if code in v.values.get(key, ())]
            if isinstance(x.get("option"), str):
                named += _values_named(led, e, by_key, x["option"])
            values = f.setdefault("values", {})
            for key, code in named:
                values[key] = sorted(set(values.get(key, [])) | {code})
            if not values:
                f.pop("values")
    return [out[k] for k in sorted(out) if out[k]["kind"] != "info" or out[k].get("fields")]


def _allowed_facts(f: Facts, led: Ledger, src: Sources, by_key: dict) -> None:
    """The public build's facts: the allow-listed ones alone (src.allowed: the seen file's, and the looks' own),
    onto the rows and values they name."""
    v = vocab_of(src)
    for x in src.allowed:
        kind = FACT_OF.get(x.get("kind"))
        e = _fact_entry(led, x) if kind else None
        if e is None:
            continue
        fact = {"allowed": kind, "fields": [y for y in x.get("fields") or [] if y in safety.ADDRESS_FIELDS]}
        if kind == "info" and not fact["fields"]:
            continue
        f.row(e, kind, fact)
        if kind == "hand_changed":
            for key, codes in (x.get("values") or {}).items():
                for code in codes if isinstance(codes, list) else []:
                    if code in v.values.get(key, ()):
                        f.option(key, code, kind, fact)
            if isinstance(x.get("option"), str):
                _option_fact(f, led, e, by_key, x["option"], kind, fact)


def _look_entry(led: Ledger, lk: dict) -> dict | None:
    path = lk.get("path") or []
    es = led.find(path, lk.get("mode"), lk.get("tab"), lk.get("group")) or led.find(path, None, lk.get("tab"), None) \
        or led.find(path)
    return es[0] if es else None


def _facts(led: Ledger, src: Sources, by_key: dict) -> Facts:
    f = Facts()
    if not src.private:
        _allowed_facts(f, led, src, by_key)
        return f
    v = vocab_of(src)
    labels = v.label_set
    volatile = _volatile(src)
    # looks: the latest per (row, did, option) alone (a retraction leaves none)
    for line, lk in latest_looks(src.looks):
        if lk.get("did") == "lap" or named_placeholder(src, lk.get("path")):
            continue                        # a lap; a placeholder the crawls name (no row of its own)
        e = _look_entry(led, lk)
        if e is None:
            led.unresolved.append({"line": line, "path": lk.get("path"), "tab": lk.get("tab")})
            continue
        cite = {"look": line, "run": lk.get("run"), "t": lk.get("t"), "by": lk.get("by"), "kit": lk.get("kit")}
        changed = [k for k in lk.get("records_changed") or [] if record_base(k) not in volatile]
        res, did = lk.get("result"), lk.get("did")
        fact = {**cite, "result": res, "did": did, "screen": lk.get("screen"), "fields": lk.get("fields") or [],
                "blocker": lk.get("blocker"), "kit_message": lk.get("kit_message"), "option": lk.get("option"),
                "records": changed, "options": lk.get("options") or [], "start_sha256": lk.get("start_sha256")}
        opt = lk.get("option")
        if res == "changed" or changed:
            for k in changed:
                f.changed_records.setdefault(record_base(k), []).append(cite)
            kind = "hand_changed" if lk.get("by") == "hand" else "changed"
            f.row(e, kind, fact)
            if opt and kind == "hand_changed":
                _option_fact(f, led, e, by_key, opt, kind, fact)
        elif res == "no_change":
            fields = info_fields(lk, v)
            if did == "choose":
                f.row(e, "choose_nochange", fact)
                if opt:
                    _option_fact(f, led, e, by_key, opt, "choose_nochange", fact)
            elif fields:
                f.row(e, "info", {**fact, "fields": fields})
            else:
                f.row(e, "looked", fact)
            f.row(e, "no_change_any", fact)
        elif res == "acted":
            f.row(e, "acted", fact)
        elif res in ("refused", "greyed"):
            b = lk.get("blocker") or {}
            f.row(e, "equipment" if b.get("equipment") else "greyed", fact)
            if opt:
                _option_fact(f, led, e, by_key, opt, "greyed", fact)
        elif res == "kit_failed" and KIT_DETERMINISTIC.match(str(lk.get("kit_message") or "")):
            f.row(e, "kit", fact)
        elif res in ("kit_failed", "not_reached"):
            f.row(e, "not_reached", fact)
        elif res == "looked":
            f.row(e, "looked", fact)
    # crawl outcomes
    crumbs = _crumbs(src)
    for run, line, r in src.crawls:
        crumb = crumbs.get(r.get("page")) or [None, None]
        _crawl_fact(f, led, run, line, r, crumb, [], labels)
    # the latest page scan of each mode: its greyed rows
    for mode, (run, model, _stamp) in src.page_models.items():
        for p in model:
            crumb = [x.strip() for x in str(p.get("breadcrumb") or "").split(" > ")]
            if len(crumb) < 2:
                continue
            for row in p.get("rows") or []:
                if row.get("greyed") is True and row.get("label"):
                    es = led.find([row["label"]], mode if mode != "S&Q" else None, crumb[0], crumb[1])
                    for e in es[:1]:
                        f.row(e, "greyed", {"scan": run, "page": " > ".join(crumb[:2]), "blocker": None})
    # proofs: refused options, options chosen with nothing changed, records changed that no setting covers
    covered = {record_base(k) for k in by_key} | {f"set:{record_base(k).split(':')[1]}" for k, s in by_key.items()
                                                  if s.get("in_sets") and k.startswith("global:")}
    closing = _closing_proofs(src)
    for run, line, p in src.proofs:
        path = p.get("path") or []
        es = led.find(path)
        cite = {"proof": line, "run": run}
        changes = [c for c in p.get("changes") or [] if isinstance(c, dict)]
        keys = {record_base(c.get("key")) for c in changes} - volatile - {None}
        for k in keys - covered:
            f.changed_records.setdefault(k, []).append(cite)
        if not es:
            continue
        e = es[0]
        label = p.get("label")
        if p.get("applied") is False:
            b = blocker_of((p.get("notice") or {}).get("text") or (p.get("notice") or {}).get("notice"), labels)
            f.row(e, "proof_refused", {**cite, "blocker": b, "option": label})
            if isinstance(label, str):
                _option_fact(f, led, e, by_key, label, "greyed", {**cite, "blocker": b})
        elif not keys and (run, line) not in closing and not p.get("network") and isinstance(label, str):
            # a network row's options are proved in their own order, the saved one anywhere among them: a proof of one
            # that changed nothing may be the saved option chosen again, so none of them counts
            _option_fact(f, led, e, by_key, label, "choose_nochange", cite)
            f.row(e, "proof_nochange", cite)
        elif keys:
            f.row(e, "proof_changed", cite)
    # failures: a refusal names its blocker; the kit's own failure is "kit cannot read" only when it comes again
    for run, line, x in src.failures:
        es = led.find(x.get("path") or [])
        if not es:
            continue
        cite = {"failure": line, "run": run}
        if x.get("blocked"):
            f.row(es[0], "greyed", {**cite, "blocker": blocker_of(x.get("blocked"), labels)})
        elif KIT_DETERMINISTIC.match(str(x.get("why") or "")):
            f.row(es[0], "kit", {**cite, "kit_message": kit_words(x.get("why"))})
        else:
            f.row(es[0], "not_reached", {**cite, "kit_message": kit_words(x.get("why"))})
    # the kit read a row it once could not: a look after its last failing look that read it (the looks file is in
    # order, and newer than the crawls and failures before it) sets the kit's failures aside
    for fx in f.by_row.values():
        ok = [c["look"] for k in ("looked", "info", "choose_nochange", "changed", "hand_changed", "acted")
              for c in fx.get(k) or [] if "look" in c]
        failed = [c["look"] for c in fx.get("kit") or [] if "look" in c]
        if ok and max(ok) > max(failed, default=0):
            fx.pop("kit", None)
    return f


def _crawl_fact(f, led, run, line, r, crumb, parent, labels):
    label = r.get("decided") or r.get("label") or ""
    if not label:
        return
    path = [*parent, label]
    es = (led.find(path, None, crumb[0], crumb[1] if not parent else None) if crumb[0] else []) or led.find(path)
    out = str(r.get("outcome") or "")
    cite = {"crawl": line, "run": run, "outcome": out}
    if es:
        e = es[0]
        if KIT_DETERMINISTIC.match(out):
            f.row(e, "kit", {**cite, "kit_message": kit_words(out)})
        elif KIT_TRANSIENT.match(out):
            f.row(e, "not_reached", {**cite, "kit_message": kit_words(out)})
        elif refused_notice(out):
            f.row(e, "greyed", {**cite, "blocker": blocker_of(r.get("notice"), labels) if r.get("notice") else None})
        elif not out.startswith("skipped"):
            f.row(e, "looked", cite)
    for sub in r.get("submenu") or []:
        if isinstance(sub, dict):
            _crawl_fact(f, led, run, line, sub, crumb, path, labels)


def _closing_proofs(src: Sources) -> set:
    """(run, line) of each attempt's last proof: the saved option chosen again, which changes nothing by design, so
    never "tested, no record changes" (an attempt cut short too: its last proof may be that one), and never a valid
    proof: its value is the start file's, inferred. A number field's proofs (kind "fields", index [field, value]) carry
    no attempt: the prover chooses each field's own start value last (camkit's proving.fields), so the last line of
    each run of lines on one row and field is that field's closing proof. Either last line is one only when it changes
    nothing (no record but the camera's volatile ones): a block cut short by a failure ends on an ordinary line, which
    is no closing proof (review B9, 2026-11-18)."""
    volatile = _volatile(src)

    def unchanged(p):
        return not {record_base(c.get("key")) for c in p.get("changes") or [] if isinstance(c, dict)} - volatile - {None}
    last = {}
    for run, line, p in src.proofs:
        a = p.get("attempt")
        if a:
            last[a] = (run, line, p)
    out = {(run, line) for run, line, p in last.values() if unchanged(p)}
    group, at = None, None
    for run, line, p in src.proofs:
        idx = p.get("index")
        key = (run, json.dumps(p.get("path")), idx[0]) if p.get("kind") == "fields" and isinstance(idx, list) \
            and len(idx) == 2 else None
        if key != group and at is not None and unchanged(at[2]):
            out.add(at[:2])
        group, at = key, ((run, line, p) if key is not None else None)
    if at is not None and unchanged(at[2]):
        out.add(at[:2])
    return out


def _row_settings(led: Ledger, e: dict) -> list:
    """The settings a row holds: placed on it or below it, tied to it (placement missing), and drawn there too, a
    proof of theirs having gone through it (_tie_through)."""
    return list(dict.fromkeys(e["settings"] + e["tied"] + e.get("through", [])))


def _option_fact(f, led, e, by_key, label, kind, fact):
    """A fact about an option (by its label) onto each value of the row's settings that the label names: by the
    option's key (camkit.match.norm), else by camkit.match.same, each label of a row judged once."""
    for k, v in _values_named(led, e, by_key, label):
        f.option(k, v, kind, fact)


def _values_named(led, e, by_key, label) -> list:
    def norm(t):
        return _memo(match.norm, t)
    same = _same
    memo = led.__dict__.setdefault("_named", {})
    if (id(e), label) in memo:
        return memo[(id(e), label)]
    table = led.__dict__.setdefault("_labels", {})
    if id(e) not in table:
        by = {}
        for k in _row_settings(led, e):
            s = by_key.get(k)
            if not s or (e["path"] and (s.get("row") or [])[:len(e["path"])] != e["path"] and k not in e["tied"]
                         and k not in e.get("through", [])):
                continue
            for v, lab in s.get("values") or []:
                if isinstance(lab, str):
                    by.setdefault(norm(lab), []).append((k, v, lab))
        table[id(e)] = by
    by = table[id(e)]
    hits = [x for x in by.get(norm(label), []) if same(x[2], label)]
    if not hits:
        hits = [x for xs in by.values() for x in xs if same(x[2], label)]
    memo[(id(e), label)] = [(k, v) for k, v, _ in hits]
    return memo[(id(e), label)]


# ---------------------------------------------------------------- statuses

def _tie_unplaced(led: Ledger, settings: list, src: Sources) -> None:
    """Settings with no row tied to the row they belong to (placement missing): the menu row their proof went through
    (the private evidence's proved.menu), the row their name is (or starts "<row>: "), and the My Menu slots onto the
    hand tables' MY_MENU_ROW."""
    tops = [e for e in led.rows if len(e["path"]) == 1]
    by_label = {}
    for e in tops:
        by_label.setdefault(plain(e["path"][0]), []).append(e)
    my_menu = set((src.camera_file.get("my_menu") or {}).get("records") or [])
    my_row = str(src.hand.get("MY_MENU_ROW") or "")
    my_entry = None
    if my_row:
        g, _, lab = my_row.rpartition(" > ")
        my_entry = next((e for e in tops if plain(e["path"][0]) == plain(lab) and (not g or plain(e["group"]) == plain(g))),
                        None)
    for s in settings:
        if s.get("row"):
            continue
        target = None
        menu = (s.get("proved") or {}).get("menu") if isinstance(s.get("proved"), dict) else None
        if menu:
            top = re.sub(r"\s*\[.*\]$", "", str(menu[0])).split(" > ")[0].strip()
            cands = by_label.get(plain(top), [])
            target = next((e for e in cands if e["tab"] == s["tab"]), cands[0] if len(cands) == 1 else None)
        if target is None:
            cands = [e for e in by_label.get(plain(s.get("name")), []) if e["tab"] == s["tab"]]
            target = cands[0] if cands else None
        if target is None and ": " in str(s.get("name")):
            cands = by_label.get(plain(str(s["name"]).split(": ")[0]), [])
            target = cands[0] if len(cands) == 1 else None
        if target is None and my_entry is not None and s.get("id") in my_menu:
            target = my_entry
        if target is not None:
            target["tied"].append(s["key"])


def _tie_through(led: Ledger, settings: list) -> None:
    """The camera draws one setting under more than one page (a subject's own page and the Auto page): a row that holds
    no setting of its own, which a proof of a setting placed on another row went through (the private evidence's
    proved.menu, the menu rows its proofs went through: proofs chosen there changed that setting's record), takes the
    setting ("through"), and so does each row above it that holds none either. A row holding a setting of its own is
    left as it is; the public build has no proved.menu, and such rows come from looks alone."""
    for s in settings:
        p = s.get("proved")
        menus = p.get("menu") if isinstance(p, dict) else None
        if not s.get("row") or not isinstance(menus, list):
            continue                                # an unplaced setting: _tie_unplaced
        tab = s.get("row_tab") or s["tab"]
        for m in menus:
            # a proof's context ("[Movie mode]") and a table's cell (" / AEL Button @0.key.0") are no rows
            path = [x.strip() for x in re.sub(r"\s*\[[^\]]*\]$", "", str(m)).split(" / ")[0].split(" > ")]
            if len(path) < 2 or not all(path) or path == list(s["row"]):
                continue
            for n in range(2, len(path) + 1):
                for e in led.find(path[:n], tab=tab):
                    if not e["settings"] and not e["tied"] and s["key"] not in e["through"]:
                        e["through"].append(s["key"])


def _row_statuses(led: Ledger, facts: Facts, by_key: dict, src: Sources) -> None:
    _tie_unplaced(led, list(by_key.values()), src)
    _tie_through(led, list(by_key.values()))
    sony, header = save_load(src.camera_file)
    frame = src.hand.get("FRAME_PROOFS") or {}
    firsts = {}
    for e in led.rows:
        if len(e["path"]) == 1:
            firsts.setdefault((e["mode"], e["tab"], plain(e["path"][0])), e)
    covered = set(records_covered(list(by_key.values())))
    for e in led.rows:
        _one_row(e, facts.of(e), by_key, sony, header, frame, covered)
    for e in led.rows:                # a label the menu repeats in a tab: the first one holds the settings
        first = firsts.get((e["mode"], e["tab"], plain(e["path"][0])))
        if len(e["path"]) == 1 and e["nth"] and first is not None and _row_settings(led, first) \
                and not _row_settings(led, e):
            e["status"] = first["status"]
            e["same_label_as"] = first["group"]
            e["_first"] = first             # its values left and options too (_values_left, decide); never written
            e.pop("cites", None)


def _one_row(e: dict, fx: dict, by_key: dict, sony: dict, header: set, frame: dict, covered: set = None) -> None:
    """The row's status from its settings and facts (the first of STATUSES that applies), and what the private form
    cites: among them the records a look saw change that no setting covers (`covered`, records_covered's keys; a
    record a setting maps is no lead)."""
    keys = list(dict.fromkeys(e["settings"] + e["tied"] + e.get("through", [])))
    ss = [by_key[k] for k in keys if k in by_key]
    states = [setting_state(s) for s in ss]
    rule, opener, never_choose, closed = None, None, False, None
    for lab in e["path"]:
        rule = rule_class(lab)
        if rule:
            opener = openers(lab)
            never_choose = bool(safety.never_choose(lab))
            break
    # closed by rule: a never-open row a look lap does not open, as if never seen (the public form knows no body's
    # records); any other never-open row a look lap opens, and is not yet tried (docs/decisions/0024)
    if rule:
        closed = next((lab for lab in e["path"] if rule_class(lab) and safety.look_lap_refused(lab, False)), None)
    e["rule"], e["opener"] = rule, opener
    if never_choose:
        e["never_choose"] = True
    if e["tied"]:
        e["placement_missing"] = sorted(e["tied"])
    cites = []

    def first_of(*kinds):
        for k in kinds:
            if fx.get(k):
                return fx[k]
        return None
    path_t = tuple(e["path"])
    status = None
    if ss and all(x == "proved" for x in states):
        status = "proved"
    elif fx.get("hand_changed") or any(s["key"] in frame and setting_state(s) is None for s in ss):
        status = "proved by hand"
        cites = fx.get("hand_changed") or []
    elif ss and all(x in ("proved", "sampled") for x in states):
        status = "sampled"
    elif excluded_under(path_t, sony, header):
        # the row the list names, or a row below it (FTP Transfer Func., "its own file", and its rows)
        under = excluded_under(path_t, sony, header)
        status = "not in the settings file (Sony)"
        if under in header and under not in sony:
            e["header"] = True
        if sony.get(under):
            e["sony_note"] = sony[under]
        if fx.get("no_change_any"):
            e["confirmed"] = True
            cites = fx["no_change_any"]
    elif not ss and (fx.get("info") or rule == "address screen" or (safety.owner_class(e["path"][-1]) ==
                                                                    safety.LIFT_SERIAL)):
        # before an action: the never-open list counts Display Serial Number among its actions, yet safety classes it a
        # serial number screen; and a row a look saw open an information screen is one. Version and Privacy Notice stay
        # actions: no public source says what they show, so only a look of theirs can make them information screens
        status = "information screen"
        if fx.get("info"):
            cites = fx["info"]
            e["fields"] = list(dict.fromkeys(x for c in fx["info"] for x in c.get("fields") or []))
        else:
            e["inferred"] = "class"
    elif not ss and (rule in ("action", "card action") or fx.get("acted")):
        status = "action, nothing to map"
        cites = fx.get("acted") or []
        if not cites:
            e["inferred"] = "class"
    elif first_of("choose_nochange", "proof_nochange") and not first_of("changed", "proof_changed"):
        status = "tested, no record changes"
        cites = first_of("choose_nochange", "proof_nochange")
    elif "needs equipment" in states or fx.get("equipment"):
        status = "needs equipment"
        eq = next((c["blocker"]["equipment"] for c in fx.get("equipment") or [] if (c.get("blocker") or {}).get(
            "equipment")), None)
        e["equipment"] = eq or next((equipment_in((s.get("unproved_reason") or {}).get("why")) or
                                     "named in its setting's reason" for s in ss
                                     if setting_state(s) == "needs equipment"), None)
        cites = fx.get("equipment") or []
    elif "no proof possible" in states and all(x is not None for x in states):
        # every setting's state known: one with neither a proof nor a reason is still to prove
        status = "no proof possible"
        e["reason"] = sorted({(s.get("unproved_reason") or {}).get("kind") for s in ss
                              if setting_state(s) == "no proof possible"} - {None})
    elif fx.get("greyed") or fx.get("proof_refused") or any(s.get("inactive_when") for s in ss):
        status = "greyed in state"
        cites = (fx.get("greyed") or []) + (fx.get("proof_refused") or [])
        blockers = [c["blocker"] for c in cites if c.get("blocker")]
        rules = [{"row": s["inactive_when"].get("name")} for s in ss if isinstance(s.get("inactive_when"), dict)]
        if blockers or rules:
            e["blocker"] = (blockers or rules)[0]
        if not cites and rules:
            e["inferred"] = "inactive_when"
    elif fx.get("kit"):
        status = "kit cannot read"
        cites = fx["kit"]
        msg = next((c.get("kit_message") for c in reversed(cites) if c.get("kit_message")), None)
        if msg:
            e["kit_message"] = msg
        e["kit"] = next((c.get("kit") for c in reversed(cites) if c.get("kit")), None)
    elif closed:
        status = "closed by rule"
    else:
        status = "not yet tried"
    e["status"] = status
    if cites:
        e["cites"] = cites
    if fx.get("changed"):
        covered = set(records_covered(list(by_key.values()))) if covered is None else covered
        new = sorted({k for c in fx["changed"] for k in c.get("records") or [] if record_base(k) not in covered})
        if new:
            e["changed_in_looks"] = new
            e.setdefault("cites_changed", fx["changed"])
    if fx.get("looked"):
        e["looked"] = len(fx["looked"])
        opts = [o for c in fx["looked"] for o in c.get("options") or []]
        if opts:
            e["options_seen"] = list(dict.fromkeys(opts))


def _option_statuses(led: Ledger, settings: list, facts: Facts, src: Sources) -> None:
    sony, _header = save_load(src.camera_file)
    frame = src.hand.get("FRAME_PROOFS") or {}
    for s in settings:
        p = s.get("proved") if isinstance(s.get("proved"), dict) else None
        linear = bool(p and (p.get("sampled") or {}).get("linear") is True)
        proved, by_sample, inferred, either = proof_values(p)
        offered_not = {x.get("value") for x in s.get("not_offered") or [] if isinstance(x, dict)}
        hand = {v for v, _ in (frame.get(s["key"]) or {}).get("values") or []} if isinstance(frame.get(s["key"]), dict) \
            else set()
        state = setting_state(s)
        row = s.get("row") or []
        closed = next((rule_class(x) for x in row if rule_class(x)), None)
        in_sony = bool(excluded_under(tuple(row), sony, set()))
        values, cites = {}, {}
        for v, _lab in s.get("values") or []:
            fx = facts.by_option.get((s["key"], v), {})
            if v in proved or linear:
                st = "proved"
            elif v in either:
                st = PROVED_OR_SHARED
            elif v in hand or fx.get("hand_changed"):
                st = "proved by hand"
            elif v in by_sample:
                st = "sampled"
            elif v in offered_not:
                st = "not offered"
            elif in_sony:
                st = "not in the settings file (Sony)"
            elif fx.get("choose_nochange"):
                st = "tested, no record changes"
                cites[v] = fx["choose_nochange"]
            elif state == "needs equipment":
                st = "needs equipment"
            elif state == "no proof possible":
                st = "no proof possible"
            elif fx.get("greyed"):
                st = "greyed in state"
                cites[v] = fx["greyed"]
            elif closed:
                st = "closed by rule"
            else:
                st = "not yet tried"
            values[v] = INFERRED if st in INFERABLE and v in inferred else st
        if values:
            led.options.append({"key": s["key"], "path": row, "mode": s.get("row_mode") or MENU_MODE,
                                "values": values, "cites": cites})


def proof_values(p: dict | None) -> tuple:
    """(proved, sampled, inferred, either): a setting's proof's values as the ledger reads them, the one reading for
    both forms (docs/decisions/0025). A whole proof (the private build, its names there) says value by value: proved,
    those its lean form lists that no rule named from another setting's proof nor a sample between its points (chosen
    on the setting, or a held value a hand table names); sampled, those named "sampled"; inferred, those the writer named
    from a shared list (camkit.definitions.inferred). A proof read lean (the public build) says what the public file
    says: its listed values proved, or sampled for a scale off its line, or, where the setting carries the mark
    (proved.shared), either (proved or inferred, the file does not say which)."""
    if not p:
        return set(), set(), set(), set()
    listed = set(definitions.lean_proof(p).get("values") or [])
    off_line = "sampled" in p and (p.get("sampled") or {}).get("linear") is not True
    if p.get("names"):
        chosen = set(p.get("values") or [])
        by_sample = {int(v) for v, src in p["names"].items() if src == "sampled"} - chosen
        inferred = definitions.inferred(p)
        return listed - by_sample - inferred, by_sample, inferred, set()
    if p.get("shared"):
        return set(), set(), set(), listed
    return (set(), listed, set(), set()) if off_line else (listed, set(), set(), set())


def _values_left(led: Ledger) -> None:
    """Each row's values_left, once the values have their statuses: how many values of the settings placed on it (or
    tied to it) are still to try (LEFT: not yet tried, greyed in state, kit cannot read). A row with any is never
    settled, whatever its own status says of its settings (a setting proved on a few of its values is "proved"); a
    label the menu repeats takes the first one's. values_inferred beside it counts those inferred from a shared list
    (the private form's)."""
    by_key = {o["key"]: o for o in led.options}
    for e in led.rows:
        sts = [st for k in _row_settings(led, e) for st in (by_key.get(k) or {}).get("values", {}).values()]
        n = sum(1 for st in sts if st in LEFT)
        if n:
            e["values_left"] = n
        if INFERRED in sts:
            e["values_inferred"] = sts.count(INFERRED)
    for e in led.rows:
        first = e.get("_first")
        for k in ("values_left", "values_inferred"):
            if first is not None and first.get(k):
                e[k] = first[k]


def _cite_shared(led: Ledger) -> None:
    """In the full build (the proof lines are this computer's): a value the writer named from a shared list (INFERRED,
    _option_statuses, from the definition's names: the ledger infers nothing itself, docs/decisions/0025) cites the
    setting of its shared list (shared_lists) it is proved on, before what it was (a notice that greyed it, its
    blocker), where the ledger's grouping finds one; the option carries the list's other settings and its own grounds
    (shared_list). The list's own check (unborne) is said by kit/tools/coverage.py --shared and decides nothing."""
    if not led.src.private:
        return
    opts = {o["key"]: o for o in led.options}
    for x in shared_lists(led):
        for k in x["keys"]:
            o, done = opts[k], False
            for v, st in o["values"].items():
                on = [t for t in x["proved"].get(v, []) if t != k]
                if st == INFERRED and on:
                    o["cites"][v] = [{"proved_on": on[0]}] + list(o["cites"].get(v) or [])
                    done = True
            if done:
                own = x["own"][k]
                o["shared_list"] = {"with": [t for t in x["keys"] if t != k], "own_proved": len(own["proved"]),
                                    "own_proofs": [{"proof": c["proof"], "run": c["run"]} for c in own["proofs"]]}


def unborne(led: Ledger, x: dict) -> list:
    """[(key, how many values inferred, why)] of the settings of a shared list (shared_lists) whose values the writer
    named from the list (INFERRED) where the list's own proof lines do not bear that out: a line of the setting's own
    reads a value as another than it wrote (a contradiction), or its own record shows fewer than SHARED_OWN of the
    list's values as the list names them. The ledger's check beside the writer's rule, said, deciding nothing."""
    opts = {o["key"]: o for o in led.options}
    wrong = {c["key"] for c in x["contradictions"]}
    out = []
    for k in x["keys"]:
        n = sum(1 for st in opts[k]["values"].values() if st == INFERRED)
        if not n:
            continue
        if k in wrong:
            out.append((k, n, "a proof line of its own reads a value as another"))
        elif len(own_values(x, k)) < SHARED_OWN:
            out.append((k, n, f"its own record shows {len(own_values(x, k))} of the list's values (the check asks "
                              f"{SHARED_OWN})"))
    return out


# ---------------------------------------------------------------- shared lists (one picker's slots, one table of codes)

# the statuses that say a value is proved on a setting: what a shared list lends, and what a setting's own record shows
PROVED_VALUE = ("proved", "proved by hand")


def shared_lists(led: Ledger) -> list:
    """The shared lists, settings that store one table of codes, as the definition draws them: settings that list the
    same values under the same names, two at least, and either sit on one menu row (placed on it, or tied to it; none a
    copy of another setting, copy_of: a picker's slots) or are elements of one array record (a profile's parameter, one
    element a profile), none of them a readout or a copy the camera writes with another setting (scalar false); settings
    joined by either way are one list. Each {"row": the first setting's row entry (None for none), "rows", "keys",
    "values": [[value, name]], "proved": {value: [the keys it is proved on]}, "own": {key: {"proved": [its proved
    values], "proofs": [{"proof", "run", "value"}: its own proof lines that agree with the list]}}, "contradictions":
    [{"key", "proof", "run", "wrote", "reads_as"}], "never_proved": [values none is proved on, that a setting still has
    to try], "no_own": [keys with a value still to try whose own record shows no value]}; the proof lines where this
    computer holds the runs (_list_proofs). Kept on the ledger (_cite_shared, unborne and shared_view read it). The
    lists are the ledger's own grouping, a view beside the writer's inference, which decides (docs/decisions/0025)."""
    if getattr(led, "_shared", None) is not None:
        return led._shared
    by_key = {s["key"]: s for s in led.src.definition.get("settings") or []}
    opts = {o["key"]: o for o in led.options}
    order = {k: i for i, k in enumerate(by_key)}
    found, names, row_of = {}, {}, {}
    for e in led.rows:
        if e.get("_first") is not None:
            continue
        for k in dict.fromkeys(e["settings"] + e["tied"]):
            s = by_key.get(k)
            if s is None or k not in opts or (k not in e["tied"] and (s.get("row") or []) != e["path"]):
                continue                            # a setting of a deeper row, counted on its own
            row_of.setdefault(k, e)
            for v, lab in s.get("values") or []:
                if isinstance(lab, str):
                    names.setdefault(id(e), {}).setdefault(v, set()).add(lab)
            if not s.get("copy_of") and s.get("scalar") is not False:
                found.setdefault(("row", id(e), json.dumps(s.get("values"))), []).append(k)
    for k, s in by_key.items():
        m = re.fullmatch(r"(.+)\[\d+\]", k)
        if m and k in opts and s.get("scalar") is not False:
            found.setdefault(("array", m.group(1), json.dumps(s.get("values"))), []).append(k)
    # settings joined by a row or an array are one list (the same values, either way)
    parent = {}

    def root(k):
        while parent.setdefault(k, k) != k:
            k = parent[k]
        return k
    for keys in found.values():
        for k in keys[1:]:
            parent[root(k)] = root(keys[0])
    joined = {}
    for keys in found.values():
        if len(keys) >= 2:
            joined.setdefault(root(keys[0]), set()).update(keys)
    out = []
    for members in joined.values():
        keys = sorted(members, key=order.get)
        values = [list(x) for x in by_key[keys[0]]["values"]]
        rows = list({id(row_of[k]): row_of[k] for k in keys if k in row_of}.values())
        named = {}
        for e in rows:
            for v, labs in names.get(id(e), {}).items():
                named.setdefault(v, set()).update(labs)
        for v, lab in values:
            named.setdefault(v, set()).add(lab)
        proved = {v: [k for k in keys if opts[k]["values"].get(v) in PROVED_VALUE] for v, _ in values}
        # what is left to try: the values some setting still has to try, the settings with such a value
        left = {(k, v) for k in keys for v, _ in values if opts[k]["values"].get(v) in LEFT}
        out.append({"row": rows[0] if rows else None, "rows": rows, "keys": keys, "values": values,
                    "proved": {v: ks for v, ks in proved.items() if ks},
                    "own": {k: {"proved": [v for v, _ in values if opts[k]["values"].get(v) in PROVED_VALUE],
                                "proofs": []} for k in keys},
                    "contradictions": [], "never_proved": [v for v, _ in values if not proved[v]
                                                           and any((k, v) in left for k in keys)],
                    "_names": named, "_left": {k for k, _ in left}})
    out.sort(key=lambda x: order[x["keys"][0]])
    _list_proofs(led, out)
    for x in out:
        x["no_own"] = [k for k in x["keys"] if not own_values(x, k) and k in x["_left"]]
        x.pop("_names")
        x.pop("_left")
    led._shared = out
    return out


def own_values(lst: dict, key: str) -> set:
    """The values a setting's own record shows agreeing with its shared list: those it is proved on, and those its own
    proof lines wrote and read as the list names them."""
    own = lst["own"][key]
    return set(own["proved"]) | {c["value"] for c in own["proofs"]}


def _list_proofs(led: Ledger, lists: list) -> None:
    """Each shared list's proof lines (the runs' proofs.jsonl, where this computer holds them): a line that changed a
    slot of the list (a record, or an element of an array record) is that slot's own; it agrees when one of its readings
    (pass 1's map label, the OCR reading, the reader's, a vote) names the value it wrote as a setting of the row names
    it (camkit.match.same), or reads as another slot's proof of that value read. A line that agrees with nothing and
    changed one slot alone contradicts the list when two independent readings (readings, _independent) name one other
    value of it, a name the row gives the written value aside; a line that changed several slots counts only where it
    agrees (the others moved with it). A value written that the list does not hold contradicts the slot too."""
    member = {k: x for x in lists for k in x["keys"]}
    lines = []
    for run, line, p in led.src.proofs:
        if p.get("applied") is False:
            continue
        hits = []
        for ch in p.get("changes") or []:
            if not isinstance(ch, dict):
                continue
            a, b = ch.get("after"), ch.get("before")
            if isinstance(a, list):
                hits += [(f"{ch.get('key')}[{i}]", y) for i, y in enumerate(a)
                         if not isinstance(b, list) or i >= len(b) or b[i] != y]
            else:
                hits.append((ch.get("key"), a))
        hits = [(k, v) for k, v in hits if k in member and isinstance(v, int) and not isinstance(v, bool)]
        texts = [t for t in [p.get("label")] + [t for _, t in readings(p)] if isinstance(t, str) and t.strip()]
        for k, v in hits:
            lines.append({"key": k, "value": v, "run": run, "proof": line, "texts": texts, "alone": len(hits) == 1,
                          "p": p})
    by_value = {}
    for c in lines:
        by_value.setdefault((id(member[c["key"]]), c["value"]), []).append(c)
    for c in lines:
        x = member[c["key"]]
        held = c["value"] in {v for v, _ in x["values"]}
        named = x["_names"].get(c["value"], set())
        others = [t for o in by_value[(id(x), c["value"])] if o["key"] != c["key"] for t in o["texts"]]
        if held and (any(_same(t, n) for t in c["texts"] for n in named)
                     or any(_same(t, o) for t in c["texts"] for o in others)):
            x["own"][c["key"]]["proofs"].append({"proof": c["proof"], "run": c["run"], "value": c["value"]})
            continue
        if not c["alone"]:
            continue
        reads_as = None
        if held:
            indep = readings(c["p"])
            for v, n in x["values"]:
                if v == c["value"] or n in named:
                    continue
                srcs = [s for s, t in indep if _same(t, n)]
                if any(_independent(a, b) for i, a in enumerate(srcs) for b in srcs[i + 1:]):
                    reads_as = v
                    break
            if reads_as is None:
                continue                            # unconfirmed: no two readings name it otherwise
        x["contradictions"].append({"key": c["key"], "proof": c["proof"], "run": c["run"], "wrote": c["value"],
                                    "reads_as": reads_as})


def shared_view(led: Ledger) -> list:
    """The lines kit/tools/coverage.py --shared prints: each shared list (its row, settings, values, how many are proved
    on some setting of it, how many settings show values of their own, its contradictions, and the settings whose
    values the writer named from it where its own proof lines do not bear that out, unborne), then the values no setting
    of its list is proved on and the settings whose own record shows no value, the camera work each needs, and last the
    values the writer named from another setting on settings the ledger groups in no list (its rule beside the
    ledger's grouping, docs/decisions/0025)."""
    lists = shared_lists(led)
    by_key = {s["key"]: s for s in led.src.definition.get("settings") or []}
    opts = {o["key"]: o for o in led.options}

    def place(x):
        e = x["row"]
        where = f"{e['mode']} > {e['tab']} > {e['group']} > {' > '.join(e['path'])}" if e else "no row"
        return where + (f" and {len(x['rows']) - 1} more rows" if len(x["rows"]) > 1 else "") + \
            f" ({x['keys'][0]}, {by_key[x['keys'][0]]['name']}, ...)"
    out = [f"{len(lists)} shared list{'s' if len(lists) != 1 else ''} (settings listing the same values on one row, "
           f"or one array record's elements), {sum(len(x['keys']) for x in lists)} settings; each with a value "
           "inferred or still to try on one of its settings:"]
    quiet = 0
    for x in lists:
        sts = [opts[k]["values"].get(v) for k in x["keys"] for v, _ in x["values"]]
        if not any(st in LEFT or st == INFERRED for st in sts) and not x["contradictions"] and not x["no_own"]:
            quiet += 1
            continue
        own = [len(own_values(x, k)) for k in x["keys"]]
        out.append(f"  {place(x)}: {len(x['keys'])} settings, {len(x['values'])} values; proved on some setting: "
                   f"{len(x['proved'])}; settings showing values of their own: {sum(1 for n in own if n)} (from "
                   f"{min(own)} to {max(own)} each); inferred: {sts.count(INFERRED)}; still to try: "
                   f"{sum(1 for st in sts if st in LEFT)}; contradictions: {len(x['contradictions'])}")
        for c in x["contradictions"]:
            name = dict((v, n) for v, n in x["values"])
            out.append(f"      {c['key']} {by_key[c['key']]['name']}: proof {c['run']} line {c['proof']} wrote "
                       f"{name.get(c['wrote'], c['wrote'])!r} but reads as "
                       f"{name.get(c['reads_as']) if c['reads_as'] is not None else 'a value the list does not hold'!r}")
        for k, n, why in unborne(led, x):
            out.append(f"      {k} {by_key[k]['name']}: {n} values the writer named from this list, not borne out by "
                       f"the list's own proof lines: {why}")
    out.append(f"  ({quiet} other lists: every value proved, or settled without inference, on every setting)")
    never = [(x, v) for x in lists for v in x["never_proved"]]
    out.append(f"values no setting of their list is proved on: {len(never)}")
    for x in lists:
        if x["never_proved"]:
            name = dict((v, n) for v, n in x["values"])
            out.append(f"  {place(x)}: " + "; ".join(f"{name[v]} ({v})" for v in x["never_proved"]))
    none = [(x, k) for x in lists for k in x["no_own"]]
    out.append(f"settings whose own record shows no value of their list: {len(none)}")
    for x, k in none:
        out.append(f"  {k} {by_key[k]['name']} ({place(x)})")
    # the writer's lists the ledger's grouping does not draw (a hold's bracket copy, a copy of another array): its rule
    # beside the ledger's, said
    grouped = {k for x in lists for k in x["keys"]}
    apart = [(o["key"], sum(1 for st in o["values"].values() if st == INFERRED)) for o in led.options
             if o["key"] not in grouped]
    apart = [(k, n) for k, n in apart if n]
    out.append(f"values the writer named from another setting, on settings in no shared list above: "
               f"{sum(n for _, n in apart)}")
    for k, n in apart:
        out.append(f"  {k} {by_key[k]['name']}: {n}")
    return out


def records_covered(settings: list) -> dict:
    """{record key: [the settings on it]}: a setting covers its own record (record_base of its key), and a live one the
    memory sets copy (in_sets) the sets' record of the same id too. A record it does not name is one no setting covers
    (unmapped): the records' statuses and kit/tools/leads.py judge it by this one rule."""
    on = {}
    for s in settings:
        base = record_base(s["key"])
        if not base:
            continue
        on.setdefault(base, []).append(s)
        if s.get("in_sets") and base.startswith("global:"):
            on.setdefault("set:" + base.split(":", 1)[1], []).append(s)
    return on


def _record_statuses(led: Ledger, settings: list, src: Sources, facts: Facts) -> None:
    on = records_covered(settings)
    leads = {}
    for part in ("live", "sets"):
        for x in (src.leads or {}).get(part) or []:
            if isinstance(x, dict) and record_base(x.get("key")):
                leads[record_base(x["key"])] = x
    keys = set(src.records) or set(on)
    for k in sorted(keys, key=lambda k: (k.split(":")[0] != "global", int(k.split(":")[1], 16))):
        size, count = src.records.get(k, (None, None))
        ss = on.get(k, [])
        entry = {"key": k}
        if size is not None:
            entry["bytes"] = size * count
        fields = [s for s in ss if "@" in s["key"]]
        states = [setting_state(s) for s in ss]
        if fields and size is not None and FIELD_BYTES * len(fields) < size * count:
            entry["status"] = "partly named"
            entry["named_bytes"] = FIELD_BYTES * len(fields)
        elif ss and all(x is not None for x in states) and any(x in ("proved", "sampled") for x in states):
            entry["status"] = "proved"
        elif ss and all(x in ("needs equipment", "no proof possible") for x in states):
            entry["status"] = "named, no proof possible"
            entry["kind"] = sorted({(s.get("unproved_reason") or {}).get("kind") for s in ss} - {None})
        elif ss:
            entry["status"] = "named, not proved"
        else:
            lead = leads.get(k)
            seen = facts.changed_records.get(k) or ([{"report": "new"}] if k in src.report_new else []) or \
                ([{"accepted": "new"}] if k in src.accepted_new else [])
            if seen or (lead and lead.get("cls") not in (None, "NEVER")):
                entry["status"] = "changed, no row attributed"
                entry["cites"] = seen or [{"leads": lead.get("cls"), "changes": lead.get("changes")}]
            elif lead and lead.get("cls") == "NEVER":
                entry["status"] = "unmapped, never seen to change"
                entry["cites"] = [{"leads": "NEVER"}]
            else:
                entry["status"] = "unmapped, not examined"
        led.records.append(entry)


# ---------------------------------------------------------------- the proofs' validity

def value_of(s: dict, after):
    """The value a change's `after` (a record's value, as camset gives it) holds for the setting `s` (a whole record,
    an element "[i]" or a byte field "@n"), or None where it cannot be told."""
    key = s["key"]
    m = re.search(r"\[(\d+)\]$", key)
    if m:
        return after[int(m.group(1))] if isinstance(after, list) and int(m.group(1)) < len(after) else None
    m = re.search(r"@(\d+)$", key)
    if m:
        if not isinstance(after, list):
            return None
        o, n = int(m.group(1)), FIELD_BYTES
        raw = after[o:o + n]
        if len(raw) != n or not all(isinstance(x, int) and 0 <= x < 256 for x in raw):
            return None
        vals = {v for v, _ in s.get("values") or []}
        for signed in (False, True):
            v = int.from_bytes(bytes(raw), "little", signed=signed)
            if not vals or v in vals:
                return v
        return None
    return after if isinstance(after, int) else None


def readings(p: dict) -> list:
    """[(source, text)] of the independent readings a proof records of the option it chose: the OCR reading under the
    cursor ("shown", source "ocr") and the vision reader's ("vlm", "reader"), and each vote a proof carries
    ({"source": "ocr:<engine>" or "reader:<model>", "text"}: camkit.reading's). pass 1's map label ("label") is none:
    the prover matched it itself before choosing."""
    out = [(src, str(p[k])) for k, src in (("shown", "ocr"), ("vlm", "reader"))
           if isinstance(p.get(k), str) and p[k].strip()]
    out += [(str(v["source"]), str(v["text"])) for v in p.get("votes") or []
            if isinstance(v, dict) and isinstance(v.get("source"), str) and isinstance(v.get("text"), str)
            and v["text"].strip()]
    return out


def _independent(a: str, b: str) -> bool:
    """Two readings' sources are independent: not one source twice, and not a family's reading beside a vote of one of
    that family ("ocr" beside "ocr:<engine>", "reader" beside "reader:<model>": it may be that engine's or that
    model's). Two engines' or two models' votes are independent."""
    return a != b and not any(x in ("ocr", "reader") and y.startswith(x + ":") for x, y in ((a, b), (b, a)))


def readings_agree(p: dict) -> tuple:
    """(how many independent readings name the option, whether two of them agree): two readings of independent sources
    (_independent) naming it alike, compared whole (camkit.match.same: "On" is not "Continuous", "ISO 100" not "ISO
    1000", "1/250" not "1/2500")."""
    rs = readings(p)
    agree = any(_independent(rs[i][0], rs[j][0]) and _same(rs[i][1], rs[j][1])
                for i in range(len(rs)) for j in range(i + 1, len(rs)))
    return len(rs), agree


def _attributed(led: Ledger, path: list, by_key: dict) -> set:
    """The records of the settings placed on the row at `path` (or tied to it), and their copies."""
    memo = led.__dict__.setdefault("_attributed", {})
    if tuple(path) not in memo:
        memo[tuple(path)] = _attributed_now(led, path, by_key)
    return memo[tuple(path)]


def _attributed_now(led: Ledger, path: list, by_key: dict) -> set:
    out = set()
    for e in led.find(path):
        for k in _row_settings(led, e):
            out.add(record_base(k))
            s = by_key.get(k) or {}
            for c in (s.get("copies") or []) + [s.get("copy_of")] + list(s.get("copy_for") or []):
                if isinstance(c, str):
                    out.add(record_base(c))
    out |= {record_base(k) for k, s in by_key.items() if (s.get("row") or [])[:len(path)] == list(path)}
    return out - {None}


def _validity(led: Ledger, by_key: dict, src: Sources) -> None:
    """Each proof checked by PROOF_VALIDITY from what proofs.jsonl holds: "valid", "inferred" (the saved option chosen
    again, an attempt's last, changing nothing: its value is the start file's) or "unchecked" naming the conditions
    missing; per (row, context, option) the first valid proof is its evidence bundle, and every proof beside it a
    repeat."""
    volatile = _volatile(src)
    closing = _closing_proofs(src)
    groups = {}
    checked = []
    for run, line, p in src.proofs:
        if not isinstance(p.get("path"), list):
            continue
        path = p["path"]
        changes = [c for c in p.get("changes") or [] if isinstance(c, dict)]
        keys = {record_base(c.get("key")) for c in changes} - volatile - {None}
        attributed = _attributed(led, path, by_key)
        inferred = (run, line) in closing and not keys
        a = bool(keys) and keys <= attributed
        n, agree = readings_agree(p)
        # the value the option wrote into the row's own settings' records alone: a side effect on another record never
        # makes two options look distinct
        own = sorted((c.get("key"), json.dumps(c.get("after"))) for c in changes if record_base(c.get("key")) in attributed)
        sig = "start" if not own else json.dumps(own)
        g = (tuple(path), p.get("context"), run)
        idx = json.dumps(p.get("index"))
        groups.setdefault(g, {})[idx] = sig
        checked.append({"run": run, "line": line, "path": path, "context": p.get("context"), "index": idx,
                        "option": p.get("label"), "a": a, "b": agree, "one_reading": n < 2, "inferred": inferred,
                        "d": p.get("attempt") in src.attempts if p.get("attempt") else None, "group": g, "p": p})
    for c in checked:
        sigs = groups[c["group"]]
        distinct = len(set(sigs.values())) == len(sigs)
        walked = src.maps.get(tuple(c["path"]))
        c["c"] = distinct and (walked is None or len(sigs) == walked)
        c["walked"] = walked
        c["missing"] = [k for k in REQUIRED if not c[k]]
        c["valid"] = not c["inferred"] and not c["missing"]
        c["state"] = "valid" if c["valid"] else "inferred" if c["inferred"] else "unchecked"
    by_option, repeats = {}, 0
    for c in checked:
        k = (tuple(c["path"]), c["context"], c["index"])
        by_option.setdefault(k, []).append(c)
    shas = {}
    for e in src.downloads:
        if e.get("path") and e.get("sha256"):
            shas[Path(str(e["path"])).name] = e["sha256"]
            shas[str(e["path"])] = e["sha256"]
    bundles = []
    for k, cs in by_option.items():
        valid = [c for c in cs if c["valid"]]
        if valid:
            repeats += len(cs) - 1
            c = valid[0]
            p = c["p"]
            bundles.append({"path": list(k[0]), "context": k[1], "option": c["option"], "run": c["run"],
                            "line": c["line"],
                            "before": {"file": p.get("base"), "sha256": shas.get(f"{c['run']}/dat/{p.get('base')}")
                                       or shas.get(str(p.get("base")))},
                            "after": {"file": p.get("dat"), "sha256": shas.get(f"{c['run']}/dat/{p.get('dat')}")
                                      or shas.get(str(p.get("dat")))},
                            "frames": [x for x in (p.get("chosen_frame"), p.get("row_frame")) if x]})
    missing = {}
    for c in checked:
        for m in c["missing"]:
            if not c["inferred"]:
                missing[m] = missing.get(m, 0) + 1
    led.proof_summary = {"proofs": len(checked), "valid": sum(c["valid"] for c in checked),
                         "inferred": sum(c["inferred"] for c in checked),
                         "unchecked": sum(c["state"] == "unchecked" for c in checked), "missing": missing,
                         "one_reading": sum(c["one_reading"] for c in checked),
                         "options_with_a_valid_proof": len(bundles), "repeats_of_a_valid_proof": repeats}
    led.bundles = bundles
    led.proof_checks = [{k: v for k, v in c.items() if k not in ("p", "group")} for c in checked]
    # each proved value: valid when one proof of the option naming it is, else what its proofs miss; a value only a
    # closing proof chose is inferred
    for c in checked:
        es = led.find(c["path"])
        if not es or not isinstance(c["option"], str):
            continue
        for k, v in _values_named(led, es[0], by_key, c["option"]):
            have = led.option_validity.get((k, v))
            if c["valid"]:
                led.option_validity[(k, v)] = "valid"
            elif c["inferred"]:
                if have is None:
                    led.option_validity[(k, v)] = "inferred (the saved option chosen again: the start file's value)"
            elif have != "valid":
                led.option_validity[(k, v)] = f"unchecked ({', '.join(c['missing'])})"
    # each proved row's tally
    per_row = {}
    for c in checked:
        t = per_row.setdefault(tuple(c["path"]), {"valid": 0, "inferred": 0, "unchecked": {}, "repeats": 0})
        if c["valid"]:
            t["valid"] += 1
        elif c["inferred"]:
            t["inferred"] += 1
        for m in (c["missing"] if not c["inferred"] else []):
            t["unchecked"][m] = t["unchecked"].get(m, 0) + 1
    for k, cs in by_option.items():
        if any(c["valid"] for c in cs):
            per_row[k[0]]["repeats"] += len(cs) - 1
    for e in led.rows:
        t = per_row.get(tuple(e["path"]))
        if t:
            e["proofs"] = t


# ---------------------------------------------------------------- the two forms

ROW_PUBLIC = ("mode", "tab", "group", "path", "nth", "status", "same_label_as", "rule", "opener", "never_choose",
              "placement_missing", "blocker", "equipment", "fields", "reason", "confirmed", "header", "sony_note",
              "inferred", "values_left")
ROW_PRIVATE = ROW_PUBLIC + ("values_inferred", "through", "source", "cites", "kit_message", "kit", "changed_in_looks",
                            "cites_changed", "looked", "options_seen", "proofs")
# a blocker's keys the public form holds: the row an inactive_when names, never an option (the state it stood in)
PUBLIC_BLOCKER_KEYS = ("row",)
ABOUT = ("What is settled about this camera's menus and file, generated by kit/tools/coverage.py --write from the "
         "public sources alone (the definition, the hand tables, the camera file, the Help Guide's menu list, "
         "camkit.safety) and the few facts a look establishes that hold for every camera of the model (an "
         "information screen and its field names, a row that acts when opened, a hand check that changed a record, "
         "a row of the maker's Save/Load list seen to change nothing): one status per row, per value of each setting "
         "and per record, in the order of precedence docs/DATA_CONTRACTS.md gives (docs/decisions/0023). Nothing "
         "observed of the camera's state, never a run, a date, a hash, a current option or a value "
         "(docs/decisions/0016).")


def _row_out(e: dict, keys, private: bool) -> dict:
    out = {}
    for k in keys:
        v = e.get(k)
        if k == "nth":
            if v:
                out[k] = v
            continue
        if v in (None, [], {}, False, 0):
            continue
        if k == "blocker" and isinstance(v, dict):
            v = {bk: bv for bk, bv in v.items() if bk in (BLOCKER_KEYS if private else PUBLIC_BLOCKER_KEYS) and bv}
            if not v:
                continue
        out[k] = v
    return out


def _doc(led: Ledger, private: bool) -> dict:
    model, _, fw = led.camera.partition("_fw")
    options = []
    for o in led.options:
        groups = {}
        for v, st in o["values"].items():
            groups.setdefault(st, []).append(v)
        options.append({"key": o["key"], "statuses": {st: groups[st] for st in STATUS_NAMES if st in groups}})
    records = []
    for r in led.records:
        x = {"key": r["key"], "status": PUBLIC_RECORD.get(r["status"], r["status"])}
        for k in ("kind", "named_bytes"):
            if r.get(k):
                x[k] = r[k]
        records.append(x)
    return {"$schema": SCHEMA_REF, "about": ABOUT, "format": FORMAT, "model": model, "firmware": fw,
            "rows": [_row_out(e, ROW_PRIVATE if private else ROW_PUBLIC, private) for e in led.rows],
            "options": options, "records": records}


def public_doc(led: Ledger) -> dict:
    """The public lean form (data/<model>_fw<fw>/coverage_<model>_fw<fw>.json), written from public_ledger(led): the
    public sources and the allow-listed facts alone, whatever else `led` was built from."""
    return _doc(public_ledger(led), private=False)


def private_doc(led: Ledger) -> dict:
    """The private form (beside the looks file), the full build's: each status with its citations, the kit's
    messages, the records seen changing, the proofs' validity and one evidence bundle per valid proof."""
    doc = _doc(led, private=True)
    doc.pop("$schema", None)
    doc["about"] = ("The private form of " + led.camera + "'s coverage ledger (kit/tools/coverage.py --write): each "
                    "status with its citations (looks, crawls, proofs, scans), the proofs' validity and one evidence "
                    "bundle per valid proof. Never published (docs/decisions/0016).")
    for o, x in zip(led.options, doc["options"], strict=True):
        if o["cites"]:
            x["cites"] = {str(v): c for v, c in o["cites"].items()}
        valid = {str(v): led.option_validity[(o["key"], v)] for v in o["values"] if (o["key"], v) in led.option_validity}
        if valid:
            x["validity"] = valid
        if o.get("shared_list"):
            x["shared_list"] = o["shared_list"]
    doc["records"] = [dict(r) for r in led.records]
    doc["unresolved_looks"] = led.unresolved
    doc["proofs"] = led.proof_summary
    doc["bundles"] = led.bundles
    return doc


def text(doc: dict) -> str:
    """The form as written: its keys in order, each row, option and record on a line of its own (deterministic: the
    same ledger gives the same bytes)."""
    lines = ["{"]
    items = list(doc.items())
    for i, (k, v) in enumerate(items):
        end = "," if i < len(items) - 1 else ""
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            lines.append(f" {json.dumps(k)}: [")
            for j, x in enumerate(v):
                lines.append("  " + json.dumps(x, ensure_ascii=False) + ("," if j < len(v) - 1 else ""))
            lines.append(" ]" + end)
        else:
            lines.append(f" {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}{end}")
    lines.append("}")
    return "\n".join(lines) + "\n"


def vocabulary(camera: str, data_dir: Path = None) -> Vocab | None:
    """The closed vocabulary of a camera's public form (Vocab), from its public definition (definitions.path) and the
    data folder's Help Guide list and camera file (`data_dir`, else the camera's own); None with no definition."""
    p = definitions.path(camera)
    if not p.exists():
        return None
    ddir = Path(data_dir) if data_dir is not None and Path(data_dir).is_dir() else definitions.data_dir(camera)
    try:
        help_rows = jsonl.read(ddir / f"help_guide_menu_{camera}.jsonl", bad="skip")
    except (OSError, ValueError):
        help_rows = []
    return Vocab(definitions.load_public(p), help_rows, _read_json(ddir / f"camera_{camera}.json") or {})


def schema_problems(doc, schema_name: str = "coverage") -> list:
    """Where a public form (or its seen file, schema_name "coverage-seen") breaks its schema in schemas/, in words (at
    most five)."""
    try:
        import jsonschema
    except ImportError:
        return ["jsonschema is not installed (kit/requirements.txt): the schema could not be checked"]
    schema = json.loads((ROOT / "schemas" / f"{schema_name}.schema.json").read_text(encoding="utf-8"))
    errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(doc), key=lambda e: list(e.absolute_path))
    return [f"schema: {'/'.join(str(x) for x in e.absolute_path) or 'top'}: {e.message[:160]}" for e in errs[:5]]


def _head_problems(doc, camera: str, about: str, schema_ref: str) -> list:
    out = []
    model, _, fw = str(camera).partition("_fw")
    if doc.get("model") != model or doc.get("firmware") != fw:
        out.append(f"model and firmware are not {camera}'s")
    if doc.get("about") != about:
        out.append("about is not the kit's own words")
    if doc.get("$schema", schema_ref) != schema_ref:
        out.append("$schema is not the schema's path")
    return out


def _place_problems(r: dict, w: str, vocab: Vocab, bad) -> None:
    if r.get("mode") not in MODES:
        bad(w, "mode", r.get("mode"))
    if r.get("tab") not in vocab.tab_set:
        bad(w, "tab", r.get("tab"))
    if r.get("group") not in vocab.group_set and r.get("group") != "":
        bad(w, "group", r.get("group"))
    for x in r.get("path") or []:
        if x not in vocab.label_set:
            bad(w, "label", x)
    for x in r.get("fields") or []:
        if x not in vocab.fields:
            bad(w, "field", x)


def vocabulary_problems(doc, vocab: Vocab | None, camera: str) -> list:
    """Where a public form holds a word its closed vocabulary does not (Vocab): a row's path, a blocker's row or
    same_label_as that no public source names, a field that is not one of the kit's address field names, an equipment,
    a note or a reason kind of another wording, a mode, tab or group no source has, an about other than the kit's own;
    and a status a state seen or a kit's failure gives (NEVER_PUBLIC), a "greyed in state" not inferred from an
    inactive_when, a value greyed. Nothing is free text."""
    if not isinstance(doc, dict):
        return ["not a JSON object"]
    if vocab is None:
        return [f"no definition for {camera}: the form's words cannot be checked against it"]
    out = _head_problems(doc, camera, ABOUT, SCHEMA_REF)

    def bad(where, what, word):
        out.append(f"{where}: {what} {word!r} is no word of the public sources")
    for i, r in enumerate(doc.get("rows") or []):
        if not isinstance(r, dict):
            continue
        w = f"rows[{i}]"
        _place_problems(r, w, vocab, bad)
        if "same_label_as" in r and r["same_label_as"] not in vocab.group_set:
            bad(w, "same_label_as", r["same_label_as"])
        b = r.get("blocker")
        if b is not None and (not isinstance(b, dict) or set(b) - set(PUBLIC_BLOCKER_KEYS)
                              or b.get("row") not in vocab.label_set):
            bad(w, "blocker", b)
        if "equipment" in r and r["equipment"] not in EQUIPMENT_NAMES:
            bad(w, "equipment", r["equipment"])
        if "sony_note" in r and r["sony_note"] not in vocab.notes:
            bad(w, "sony_note", r["sony_note"])
        for x in r.get("reason") or []:
            if x not in vocab.kinds:
                bad(w, "reason", x)
        st = r.get("status")
        if st in NEVER_PUBLIC:
            out.append(f"{w}: the status {st!r} rests on what this computer's runs hold, never public")
        if st == "greyed in state" and r.get("inferred") != "inactive_when":
            out.append(f"{w}: \"greyed in state\" in public is the definition's inactive_when alone")
    for i, o in enumerate(doc.get("options") or []):
        if not isinstance(o, dict):
            continue
        for st in o.get("statuses") or {}:
            if st in NEVER_PUBLIC or st == "greyed in state":
                out.append(f"options[{i}]: the status {st!r} rests on what this computer's runs hold, never public")
    for i, r in enumerate(doc.get("records") or []):
        for x in (r.get("kind") or []) if isinstance(r, dict) else []:
            if x not in vocab.kinds:
                bad(f"records[{i}]", "kind", x)
    return out


def _text_problems(doc, raw: str = None) -> list:
    """A key of PRIVATE_KEYS at any depth; in any text a hash or a kit commit (seven hex digits or more), a date (a time
    after it too) or a run's folder; in the whole text a run's name or a date (definitions.RUN_OR_DAY)."""
    out = []

    def walk(x, where):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in PRIVATE_KEYS:
                    out.append(f"the key {k!r} ({where or 'top'}): private evidence")
                walk(v, f"{where}.{k}" if where else k)
        elif isinstance(x, list):
            for i, v in enumerate(x):
                walk(v, f"{where}[{i}]")
        elif isinstance(x, str):
            for rx, what in ((HEX_RUN, "a hash or a kit commit"), (DATE, "a date"), (RUN_FOLDER, "a run's folder")):
                m = rx.search(x)
                if m:
                    out.append(f"{what} in {where or 'top'} ({m.group(0)!r})")
    walk(doc, "")
    raw = raw if raw is not None else json.dumps(doc)
    return out + [f"names {m!r}" for m in sorted(set(definitions.RUN_OR_DAY.findall(raw)))]


def _vocab_for(doc, vocab, camera, data_dir) -> tuple:
    camera = camera or (f"{doc.get('model')}_fw{doc.get('firmware')}" if isinstance(doc, dict) else "")
    if vocab is None and isinstance(doc, dict):
        try:
            vocab = vocabulary(camera, data_dir)
        except (SystemExit, OSError, ValueError):
            vocab = None
    return vocab, camera


def public_problems(doc, raw: str = None, vocab: Vocab = None, camera: str = None, data_dir: Path = None) -> list:
    """Where a public coverage form holds what decision 16 keeps private, in words; [] for a lean one: _text_problems,
    what the schema refuses (schemas/coverage.schema.json) and any word outside its closed vocabulary
    (vocabulary_problems: `vocab`, else the camera's, `camera` or the form's own model and firmware, its Help Guide list
    and camera file in `data_dir`). That the form is the public build of its sources and seen file, check_public asks
    besides (build_problems)."""
    vocab, camera = _vocab_for(doc, vocab, camera, data_dir)
    return _text_problems(doc, raw) + schema_problems(doc) + vocabulary_problems(doc, vocab, camera)


def seen_problems(doc, raw: str = None, vocab: Vocab = None, camera: str = None, data_dir: Path = None) -> list:
    """Where a seen file holds what decision 16 keeps private or a word its closed vocabulary does not, in words:
    _text_problems, its schema (schemas/coverage-seen.schema.json), and in each fact a mode, tab, group or row label no
    public source has, a field that is not one of the kit's address field names, a value not of the setting it names;
    an about other than the kit's own."""
    vocab, camera = _vocab_for(doc, vocab, camera, data_dir)
    out = _text_problems(doc, raw) + schema_problems(doc, "coverage-seen")
    if not isinstance(doc, dict):
        return out
    if vocab is None:
        return out + [f"no definition for {camera}: the seen file's words cannot be checked against it"]
    out += _head_problems(doc, camera, SEEN_ABOUT, SEEN_SCHEMA_REF)

    def bad(where, what, word):
        out.append(f"{where}: {what} {word!r} is no word of the public sources")
    for i, x in enumerate(doc.get("facts") or []):
        if not isinstance(x, dict):
            continue
        _place_problems(x, f"facts[{i}]", vocab, bad)
        for key, codes in (x.get("values") or {}).items() if isinstance(x.get("values"), dict) else ():
            for code in codes if isinstance(codes, list) else [codes]:
                if code not in vocab.values.get(key, ()):
                    bad(f"facts[{i}]", "value", f"{key} {code}")
    return out


def public_build_text(camera: str, data_dir: Path = None, definition: Path = None) -> str:
    """The public form as the camera's public sources and its seen file give it (public_build), as written."""
    return text(public_doc(public_build(camera, data_dir, definition)))


def build_problems(p: Path, definition: Path = None) -> list:
    """Where the committed public form at `p` is not, byte for byte, the public build of its camera's public sources
    and the seen file beside it (`definition`: the definition file of the same commit, else the camera's own): a hand
    edit of the form (a status, an equipment, a field) is one, which only kit/tools/coverage.py --write mends; the facts
    a look established live in the seen file alone. check_public runs it on the tree, and on each commit of a range
    with that commit's definition and data folder (its sample beside the definition) taken out of git."""
    camera = Path(p).parent.name
    try:
        want = public_build_text(camera, Path(p).parent, definition)
    except (SystemExit, OSError, ValueError) as e:
        return [f"its public build could not be made ({type(e).__name__}: {e})"]
    if Path(p).read_text(encoding="utf-8") != want:
        return [f"it is not the public build of {camera}'s public sources and its seen file, seen_{camera}.json (an "
                "edit by hand, or a definition changed since): kit/tools/coverage.py --write"]
    return []


def seen_doc(camera: str, facts: list) -> dict:
    model, _, fw = camera.partition("_fw")
    return {"$schema": SEEN_SCHEMA_REF, "about": SEEN_ABOUT, "format": FORMAT, "model": model, "firmware": fw,
            "facts": facts}


def _replace(p: Path, t: str, private: bool = False) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".part")
    tmp.write_text(t, encoding="utf-8", newline="\n")
    if private and os.name != "nt":
        os.chmod(tmp, 0o600)
    tmp.replace(p)
    return p


def write(led: Ledger, public_path: Path = None, private_path: Path = None, seen_path: Path = None) -> list:
    """The public form, its seen file and (unless private_path is False) the private form written; the paths written.
    The seen file (public_seen: the committed facts with the looks' own, the looks' retractions taking committed ones
    out) is written where the looks file is on this computer, or where there is none yet; the public form is the build
    of the public sources and those facts, so check_public finds it the public build. A form or a seen file
    public_problems or seen_problems refuses is not written (ValueError)."""
    out = []
    pub = Path(public_path) if public_path is not None else public_file(led.camera)
    seen = Path(seen_path) if seen_path is not None else seen_file(led.camera, led.src.given.get("data_dir"))
    vocab = vocab_of(public_ledger(led).src)
    t = text(public_doc(led))
    why = public_problems(json.loads(t), t, vocab=vocab, camera=led.camera)
    st = text(seen_doc(led.camera, public_seen(led)))
    why += seen_problems(json.loads(st), st, vocab=vocab, camera=led.camera)
    if why:
        raise ValueError(f"the public form would hold private evidence: {'; '.join(why[:3])}")
    if led.src.looks_present or not seen.exists():
        out.append(_replace(seen, st))
    out.insert(0, _replace(pub, t))
    if private_path is not False and led.src.private:
        out.append(_replace(Path(private_path) if private_path is not None else private_file(led.camera),
                            text(private_doc(led)), private=True))
    return out


# ---------------------------------------------------------------- settled

class Verdict:
    """What the ledger says of a row (or one of its options) a run is about to handle: skip, whether it counts settled
    (a run given --skip-settled leaves it out); words, the row, its status and why; reason, the line a run prints
    ("settled: <words>" for a settled one); status."""

    def __init__(self, skip: bool, words: str, status: str | None = None):
        self.skip, self.words, self.status = skip, words, status
        self.reason = f"settled: {words}" if skip else words

    def __bool__(self):
        return self.skip

    def __repr__(self):
        return f"Verdict({self.skip}, {self.reason!r})"


def _when(cites) -> str:
    for c in cites or []:
        t = c.get("t")
        if t:
            return f" ({str(t)[:10]} {c.get('by') or 'look'})"
        if c.get("run"):
            return f" ({c['run']})"
        if c.get("scan"):
            return f" (scan {c['scan']})"
    return ""


def _record_raw(path, key) -> bytes | None:
    from . import camset
    try:
        cs = camset.read(path)
    except (OSError, ValueError):
        return None
    area, rid = key.split(":")
    r = cs.get(0 if area == "global" else 1, int(rid, 16))
    return r.raw if r is not None else None


def _download_by_sha(src: Sources, sha) -> Path | None:
    for e in src.downloads:
        if e.get("sha256") == sha and src.run_root is not None:
            p = src.run_root / str(e.get("path", ""))
            if p.exists():
                return p
    return None


def ungreyed(led: Ledger, e: dict, start: Path | None) -> bool | None:
    """Whether the start file un-greys a row found greyed: by its settings' inactive_when (the record's value no longer
    among those that grey it), else by the blocker's records holding other bytes than in the file the look started
    from; None when neither can tell."""
    if start is None:
        return None
    by_key = {s["key"]: s for s in led.src.definition.get("settings") or []}
    rules = [by_key[k]["inactive_when"] for k in _row_settings(led, e) if isinstance(by_key.get(k, {}).get(
        "inactive_when"), dict)]
    if rules:
        from . import camset
        try:
            cs = camset.read(start)
        except (OSError, ValueError):
            return None
        for r in rules:
            rec = cs.get(0, int(r.get("record", -1)))
            if rec is None:
                return None
            if rec.value() in (r.get("values") or []) and rec.value() not in (r.get("except") or []):
                return False
        return True
    blocker = (e.get("blocker") or {}).get("row")
    sha = next((c.get("start_sha256") for c in e.get("cites") or [] if c.get("start_sha256")), None)
    if not blocker or not sha:
        return None
    looked_from = _download_by_sha(led.src, sha)
    recs = {record_base(s["key"]) for s in by_key.values() if any(same_label(x, blocker) for x in s.get("row") or [])}
    if looked_from is None or not recs:
        return None
    for k in recs:
        a, b = _record_raw(looked_from, k), _record_raw(start, k)
        if a is None or b is None:
            return None
        if a != b:
            return True
    return False


def decide(led: Ledger, e: dict, start: Path | None = None, option=None, judge: bool = True) -> Verdict:
    """Whether the ledger counts the row `e` (or its option, a label) settled, in words. Settled: a status of SETTLED on
    a row with no value still to try (values_left), an option by the least settled of the values its label names (one
    naming no value is not settled, whatever the row's status); greyed in state only while the start file still greys
    it (ungreyed); kit cannot read only while the kit's commit is the failing look's (kit_newer). Never: an action or an
    information screen known by its class alone (no look yet: only a run allowed to open it reaches it), and closed by
    rule, which says its opener and leaves it to the run's own guards. judge=False (a run that only prints, without
    --skip-settled) says a greyed row and a row the kit could not read by their status alone, reading no download and
    asking git nothing: nothing it says is acted on."""
    st = e.get("status")
    name = " > ".join(e["path"])
    if option is not None:
        name = f"{name} = {option!r}"
        ost = _option_status(led, e, option)
        if ost is None:
            return Verdict(False, f"{name}: no value of the row's settings is named so", st)
        st = ost
    elif e.get("values_left"):
        return Verdict(False, f"{name}: {st}, {e['values_left']} value(s) still to try", st)
    if st in SETTLED and e.get("inferred") == "class" and option is None:
        return Verdict(False, f"{name}: {st}, by its class alone (no look yet): this run's own guards decide", st)
    if st in SETTLED:
        return Verdict(True, f"{name}: {st}{_when(e.get('cites')) if option is None else ''}", st)
    if not judge and st == "greyed in state":
        b = e.get("blocker") or {}
        by = b.get("row") or b.get("equipment") or b.get("remote") or "not named"
        return Verdict(False, f"{name}: greyed in state (blocker {by})", st)
    if not judge and st == "kit cannot read":
        return Verdict(False, f"{name}: kit cannot read (at kit {e.get('kit') or 'not recorded'})", st)
    if st == "greyed in state":
        un = ungreyed(led, e, start)
        b = e.get("blocker") or {}
        by = b.get("row") or b.get("equipment") or b.get("remote") or "a blocker not named"
        if un is False:
            return Verdict(True, f"{name}: greyed in state (blocker {by}), and the start file still greys it, for now",
                           st)
        if un is True:
            return Verdict(False, f"{name}: greyed in state before, and the start file un-greys it", st)
        return Verdict(False, f"{name}: greyed in state before (blocker {by}); whether the start file un-greys it "
                              "cannot be told", st)
    if st == "kit cannot read":
        newer = kit_newer(e.get("kit"))
        if newer is False:
            return Verdict(True, f"{name}: the kit could not read it at this kit commit, until a newer one", st)
        return Verdict(False, f"{name}: the kit could not read it before; "
                              f"{'a newer kit commit' if newer else 'the kit commit cannot be compared'}", st)
    if st == "closed by rule":
        first = "; its first open on this body is the owner's own run" if any(safety.look_destructive(x)
                                                                             for x in e["path"]) else ""
        return Verdict(False, f"{name}: closed by rule ({e.get('rule')}){first}; opens with "
                              f"{', '.join(e.get('opener') or [])}: this run's own guards decide", st)
    return Verdict(False, f"{name}: {st}", st)


def _option_status(led: Ledger, e: dict, option) -> str | None:
    """The least settled status of the values of the row's settings (a repeated label's: the first one's) whose label is
    `option` (camkit.match.same), None where no value is named so."""
    if getattr(led, "_option_index", None) is None:
        led._option_index = {o["key"]: o for o in led.options}
        led._setting_index = {s["key"]: s for s in led.src.definition.get("settings") or []}
    found = []
    for k in _row_settings(led, e.get("_first") or e):
        o, s = led._option_index.get(k), led._setting_index.get(k) or {}
        for v, lab in s.get("values") or [] if o else []:
            if isinstance(lab, str) and v in o["values"] and match.same(lab, option):
                found.append(o["values"][v])
    return max(found, key=lambda st: RANK[st]) if found else None


_LEDGERS = {}


def ledger_for(camera: str, why_not: list = None) -> Ledger | None:
    """The camera's ledger for settled(), built once a process, or None when it cannot be built: no definition, or no
    looks file yet (the first run on a camera: nothing is settled until a look has been recorded). `why_not` gets the
    reason."""
    why_not = why_not if why_not is not None else []
    if camera in _LEDGERS and not _LEDGERS[camera].stale():
        return _LEDGERS[camera]
    try:
        dpath = definitions.path(camera)
    except SystemExit:
        why_not.append(f"{camera!r} is no camera's key")
        return None
    if not dpath.exists():
        why_not.append(f"no definition for {camera} ({paths.shown(dpath)})")
        return None
    if not looks_file(camera).exists():
        why_not.append(f"no looks file yet ({paths.shown(looks_file(camera))}): the first look writes it")
        return None
    try:
        led = build(camera)
    except Exception as e:      # noqa: BLE001 (a ledger that cannot be built settles nothing)
        why_not.append(f"the ledger could not be built ({type(e).__name__}: {e})")
        return None
    _LEDGERS[camera] = led
    return led


def forget() -> None:
    """The ledgers and definitions this process read, dropped (a test's camera never reaches the next test)."""
    _LEDGERS.clear()
    _PUBLIC.clear()


def settled(path, option=None, mode=None, *, tab=None, group=None, camera=None, start=None,
            ledger: Ledger = None, judge: bool = True) -> Verdict:
    """What the ledger says of the row at `path` (its labels from the top-level row; an option's label too): decide()
    on its entry (judge: decide's). Not settled when the ledger is missing or stale, when no entry is found for the
    path in that mode, tab and group (no entry of another mode stands in), nor when entries of it in several modes (no
    mode given) disagree: the least settled decides."""
    why = []
    camera = camera or (paths.camera() or (None,))[0]
    led = ledger or (ledger_for(camera, why) if camera else None)
    name = " > ".join(str(x) for x in path or [])
    if led is None:
        return Verdict(False, f"no coverage ledger ({'; '.join(why) or 'no camera named'}): nothing is settled")
    if led.stale():
        return Verdict(False, "the coverage ledger is stale (the definition, the hand tables or the camera file changed "
                              "since it was built): nothing is settled")
    es = led.find(path, mode, tab, group)
    if not es:
        return Verdict(False, f"{name}: no ledger entry for it{f' in {mode}' if mode else ''}")
    verdicts = [decide(led, e, start, option, judge) for e in es]
    held = [v for v in verdicts if not v.skip]
    return held[0] if held else verdicts[0]


# ---------------------------------------------------------------- the runs' gates (one call before, one after)

def add_skip_argument(ap, crawl: bool = False) -> None:
    """--skip-settled, for kit/crawl_run.py (crawl=True) and kit/prove_run.py; kit/drive.py never skips."""
    if crawl:
        ap.add_argument("--skip-settled", action="store_true",
                        help="leave out the rows the coverage ledger has settled (docs/decisions/0023), each said in "
                             "one line; without it every row is opened as ever and the ledger's word on each is only "
                             "printed. The crawl's map.json then has holes where it skipped: a crawl meant to build "
                             "pass 1's map must not skip (kit/pass1_map.py refuses such a crawl for kit2_pass1)")
    else:
        ap.add_argument("--skip-settled", action="store_true",
                        help="leave out a list or dialog row whose every planned option the coverage ledger has "
                             "settled (docs/decisions/0023), each said in one line; never with --context, --first, "
                             "--tables, --wb, --wb-corners, --looks, --look-base, --redo or --help-text, and never "
                             "another kind of job. Without it every row is proved as ever and the ledger's word on "
                             "each is only printed")


def _say(message: str) -> None:
    print(f"coverage: {message}", flush=True)


def _failed(where: str, e: BaseException) -> None:
    """A ledger error in a gate, said in one line: the run goes on as if the ledger were not there."""
    _say(f"{where}: the ledger failed ({type(e).__name__}: {e}); nothing changes for the run")


def _latest_download(camera: str) -> Path | None:
    try:
        from . import provenance
        root = paths.runs_top() / camera
        for e in reversed(provenance.entries(root)):
            p = root / str(e.get("path", ""))
            if p.exists():
                return p
    except Exception:       # noqa: BLE001
        return None
    return None


def _mode_of(scan) -> str | None:
    try:
        import runner
        return runner.recorded_mode(runner.scan_dir(scan))
    except (Exception, SystemExit):     # noqa: BLE001 (a scan that cannot be found names no mode)
        return None


class DriveGate:
    """kit/drive.py's: before anything connects, what the ledger says of the --path is printed in one line, and the
    run goes on whatever it says (drive.py never skips). After the run, one look line from what the run's drive.jsonl
    gained. Neither ever breaks the run nor changes its exit status."""

    def __init__(self, a):
        self.camera = self.run_dir = self.log = self.mode = None
        self.size, self.private, self.path = 0, False, []
        try:
            self.camera = (paths.camera() or (None,))[0]
            self.run_dir = (paths.runs_top() / self.camera / a.run) if self.camera else None
            self.log = self.run_dir / "drive.jsonl" if self.run_dir else None
            self.size = self.log.stat().st_size if self.log and self.log.exists() else 0
            self.path, self.mode = list(a.path), _mode_of(getattr(a, "scan", None))
            self.private = bool(getattr(a, "network", False) or getattr(a, "owner", False))
            if self.camera is not None:
                # drive.py never skips: the row's status alone, no download read and no git asked (judge=False)
                v = settled(self.path, None, self.mode, camera=self.camera, judge=False)
                _say(v.reason + ("; drive.py goes on (it never skips)" if v.skip else ""))
        except (Exception, SystemExit) as e:    # noqa: BLE001
            _failed("drive.py's gate", e)

    def after(self) -> bool:
        """One look from the run's own result line (the last drive.jsonl line it wrote); never raises."""
        try:
            if not self.log or not self.log.exists():
                return False
            with open(self.log, "rb") as f:
                f.seek(self.size)
                new = [json.loads(x) for x in f.read().decode("utf-8", "replace").splitlines() if x.strip()]
            if not new:
                return False
            return append_look(self.camera, drive_look(new[-1], self.camera, self.mode, self.run_dir.name),
                               private=self.private)
        except (Exception, SystemExit) as e:    # noqa: BLE001
            _say(f"the look was not recorded ({type(e).__name__}: {e})")
            return False


def drive_gate(a) -> DriveGate:
    return DriveGate(a)


_PUBLIC = {}


def _public(camera: str) -> dict:
    """The camera's public definition and the labels and values a look is judged by (known_labels, from it, its Help
    Guide list and its camera file; the values its settings name), read once a process; empty where there is none."""
    if camera not in _PUBLIC:
        doc, help_rows, cam = {}, [], {}
        try:
            p = definitions.path(camera)
            doc = definitions.load_public(p) if p.exists() else {}
            ddir = definitions.data_dir(camera)
            help_rows = jsonl.read(ddir / f"help_guide_menu_{camera}.jsonl", bad="skip") \
                if (ddir / f"help_guide_menu_{camera}.jsonl").exists() else []
            cam = _read_json(ddir / f"camera_{camera}.json") or {}
        except (SystemExit, OSError, ValueError):
            pass
        _PUBLIC[camera] = {"doc": doc, "labels": known_labels(doc, help_rows, cam),
                           "values": {lab for s in doc.get("settings") or [] for _v, lab in s.get("values") or []
                                      if isinstance(lab, str)}}
    return _PUBLIC[camera]


def _label_set(camera: str) -> set:
    return _public(camera)["labels"]


def _value_set(camera: str) -> set:
    return _public(camera)["values"]


def _place(camera: str, path: list) -> tuple:
    """(tab, group) of a path's top row, where the definition's menu names its label once."""
    hits = [m for m in _public(camera)["doc"].get("menu") or [] if path and same_label(m["label"], path[0])]
    return (hits[0]["tab"], hits[0]["group"]) if len(hits) == 1 else (None, None)


def _sha(p) -> str | None:
    try:
        from . import provenance
        return provenance.sha256(p) if p and Path(p).exists() else None
    except OSError:
        return None


OPENING_KEYS = ("right", "ms_right", "enter", "ms_enter")


def press_key(p) -> str:
    """A --press argument's key alone, as drive.py writes it in drive.jsonl's presses ("enter:Drive Mode", "enter!:x",
    "down@3"): what precedes its regex, its row and a vouching "!", in lower case."""
    head = str(p).split(":", 1)[0].strip().strip(safety.QUOTES)
    return head.split("@", 1)[0].removesuffix("!").strip().lower()


def drive_look(line: dict, camera: str, mode: str | None, run: str) -> dict:
    """The look a drive.jsonl result line makes: what was done (did "open" only where every press after the one that
    opened the row is a looking key, safety.LOOK_KEYS: up, down and MENU, what a look lap sends inside a row, each key
    judged as drive.py sends it, look-alike letters folded; or where none follows it, or nothing opened the row; the
    Enter that opens it, "enter:<row>", is the opening press. Any other press after it, left, right, a dial, Enter, a
    named key or C4, makes it "choose": on 2026-11-15 a slider moved and cancelled with MENU that changed a record was
    written as an open, which camkit.first_open took for a first open that failed), the screen the opening showed, its
    field names (only what the run kept: safety.kept_screen's on a private run, the known labels and field names of a
    plain screen's text), the result (a notice: greyed with its blocker as a rule, unless it shows the camera's own address
    fields and no refusal, an information screen's notice; records differing: changed; the presses cut short by a
    deterministic failure: kit_failed; the run unfinished or cut short otherwise: not_reached) and the records changed
    by key."""
    path = [str(x) for x in line.get("path") or []]
    owner = next(iter((line.get("owner") or {}).values()), {}) or {}
    place = list(owner.get("path") or [])
    tab, group = (place[0], place[1]) if len(place) >= 3 else _place(camera, path)
    presses = [press_key(p) for p in line.get("presses") or []]
    opened_at = next((i for i, p in enumerate(presses) if p in OPENING_KEYS), None)
    did = ("choose" if opened_at is not None
           and any(safety.canonical_input(p) not in safety.LOOK_KEYS for p in presses[opened_at + 1:]) else "open")
    screens = [s for s in line.get("screens") or [] if isinstance(s, dict)]
    opened = next((s for s in screens if press_key(s.get("after", "")) in OPENING_KEYS), screens[0] if screens else {})
    kind = opened.get("kind")
    labels = _label_set(camera)
    fields = []
    for s in screens:
        if "fields" in s:
            fields += [x for x in s.get("fields") or [] if isinstance(x, str)]
        elif isinstance(s.get("text"), str) and s.get("kind") in FIELD_KINDS:
            fields += safety.screen_fields(s["text"].splitlines(), labels, _value_set(camera))[0]
    fields = list(dict.fromkeys(fields))
    changes = [c.get("key") for c in line.get("changes") or [] if isinstance(c, dict) and c.get("key")]
    blocker, words = None, ""
    if kind == "notice":
        words = opened.get("notice") or opened.get("text") or ""
        blocker = blocker_of(words, labels)
    # a notice that refuses nothing the kit knows and shows the camera's own address fields: an information screen's
    info_notice = kind == "notice" and not blocker and not safety.notice_refuses(words) and \
        any(x in safety.ADDRESS_FIELDS for x in fields)
    outcome = str(line.get("outcome") or "")
    if line.get("restore") in ("not finished", "by hand") or line.get("after") is None and "changes" not in line:
        result = "not_reached"
    elif not line.get("completed", True):
        result = "kit_failed" if KIT_DETERMINISTIC.match(outcome) else "not_reached"
    elif kind == "notice" and not info_notice:
        result = "greyed"
    elif changes:
        result = "changed"
    else:
        result = "no_change"
    decision = None
    if line.get("network"):
        decision = "network " + ", ".join(sorted({str(v) for v in line["network"].values()}))
    elif owner:
        decision = f"owner {owner.get('date', '')}".strip()
    return {"t": now(), "run": run, "kit": kit_commit(), "by": "drive", "mode": mode, "tab": tab, "group": group,
            "path": path, "option": None, "did": did, "screen": kind, "result": result, "blocker": blocker,
            "fields": fields,
            "kit_message": kit_words(outcome) if result in ("kit_failed", "not_reached") else None,
            "decision": decision,
            "start_sha256": _sha(Path(paths.runs_top() / camera / run / "dat" / str(line.get("before")))
                                 if line.get("before") else None),
            "end_sha256": _sha(Path(paths.runs_top() / camera / run / "dat" / str(line.get("after")))
                               if line.get("after") else None),
            "records_changed": [k for k in changes if RECORD_KEY.match(str(k))]}


class CrawlGate:
    """kit/crawl_run.py's: skip(page, row) before a row is opened (camkit.crawl): it prints what the ledger says of the
    row, and only on a --skip-settled run gives why a settled row is not opened; after(row, model) for each row's
    summary, lap(ending) at the run's end. None of them ever breaks the run."""

    def __init__(self, run, a, start: Path | None):
        self.led, self.skipping, self.start, self.start_sha = None, False, start, None
        self.camera = self.run = self.mode = None
        self.private = False
        try:
            self.camera, self.run = run.root.name, run.dir.name
            self.skipping = bool(getattr(a, "skip_settled", False))
            self.mode = _mode_of(getattr(a, "scan", None))
            self.private = bool(getattr(a, "network", False))
            self.start_sha = _sha(start)
            why = []
            self.led = ledger_for(self.camera, why)
            if self.led is None:
                _say(f"no coverage ledger ({'; '.join(why)}): nothing is settled, no row is skipped")
            elif self.skipping:
                _say("--skip-settled: a row the ledger has settled is not opened, and this crawl's map.json has a hole "
                     "there (kit/pass1_map.py refuses such a crawl for pass 1's map)")
        except (Exception, SystemExit) as e:    # noqa: BLE001
            self.led = None
            _failed("crawl_run.py's gate", e)

    def skip(self, page: dict, row: dict, opened: bool = True) -> str | None:
        """Why a --skip-settled run leaves the row out (settled), else None, the ledger's word printed; `opened` False
        where the lap leaves the row unopened all the same (camkit.crawl.left_unopened: never-open, or not seen opened
        on this body without a first open), whose line then never says it is opened."""
        try:
            if self.led is None:
                return None
            crumb = [x.strip() for x in str(page.get("breadcrumb") or "").split(" > ")]
            v = settled([row.get("label") or ""], None, self.mode, tab=crumb[0] if crumb else None,
                        group=crumb[1] if len(crumb) > 1 else None, camera=self.camera, start=self.start,
                        ledger=self.led, judge=self.skipping)
            if self.skipping and v.skip:
                return v.reason                 # the row's outcome: "skipped: settled: ..." (CRAWL_SKIPPED)
            _say(v.reason + ("; opened all the same (--skip-settled leaves it out)" if v.skip and opened else ""))
            return None
        except (Exception, SystemExit) as e:    # noqa: BLE001
            _failed("crawl_run.py's gate", e)
            return None

    def after(self, row: dict, model: dict, hold=None) -> None:
        """The row's looks written; `hold(look)` keeps back one it returns True for (camkit.first_open.FirstOpens.takes:
        a row's first open not yet checked)."""
        try:
            page = model.get(row.get("page")) or next((p for p in model.values() if isinstance(p, dict)
                                                        and p.get("page") == row.get("page")), {})
            crumb = [x.strip() for x in str(page.get("breadcrumb") or "").split(" > ")]
            for lk in crawl_looks(row, crumb, self.mode, self.run, self.camera):
                lk["start_sha256"] = self.start_sha
                if hold is None or not hold(lk):
                    append_look(self.camera, lk, private=self.private)
        except (Exception, SystemExit) as e:    # noqa: BLE001
            _say(f"the look was not recorded ({type(e).__name__}: {e})")

    def lap(self, ending) -> None:
        try:
            changes = [c.key for c in getattr(ending, "changes", None) or []]
            after = getattr(ending, "after", None)
            append_look(self.camera, {"t": now(), "run": self.run, "kit": kit_commit(), "by": "crawl",
                                      "mode": self.mode, "path": [], "did": "lap",
                                      "result": "changed" if changes else "no_change",
                                      "start_sha256": self.start_sha, "end_sha256": _sha(after),
                                      "records_changed": [k for k in changes if RECORD_KEY.match(k)]},
                        private=self.private)
        except (Exception, SystemExit) as e:    # noqa: BLE001
            _say(f"the lap's look was not recorded ({type(e).__name__}: {e})")


def crawl_gate(run, a, start) -> CrawlGate:
    return CrawlGate(run, a, start)


def crawl_skipped(run, prefix: str = CRAWL_SKIPPED) -> int:
    """How many rows of a crawl's rows.jsonl, its submenus' included, a run left out with an outcome led by `prefix`: a
    --skip-settled run's (CRAWL_SKIPPED), whose map has a hole at each, or a first open's rule's
    (camkit.first_open.SKIPPED)."""
    def count(rows) -> int:
        return sum(str(r.get("outcome") or "").startswith(prefix) + count(r.get("submenu") or [])
                   for r in rows if isinstance(r, dict))
    return count(_jsonl(Path(run) / "rows.jsonl"))


def crawl_looks(row: dict, crumb: list, mode, run: str, camera: str, parent=()) -> list:
    """The looks a crawl's row summary (kit/crawl_run.py's, kept_row's on a --network run) makes: one for the row and
    one for each row of a submenu it crawled; none for a row it skipped. A walked row was looked at (the lap's diff,
    written by lap(), says whether anything changed); a notice greyed it, a notice --info-ok named and did not pass
    too, while one it passed was looked at (refused_notice); an unknown screen or no response to Right is kit_failed
    (it comes again until the kit changes); a lost row, an error or a walk cut short is not_reached."""
    label = row.get("decided") or row.get("label") or ""
    out = str(row.get("outcome") or "")
    if not label or label.startswith("(") or out.startswith("skipped"):
        return []               # no row the kit knows (a label withheld), or one it did not open
    path = [*parent, label]
    if KIT_DETERMINISTIC.match(out):
        result, msg = "kit_failed", kit_words(out)
    elif KIT_TRANSIENT.match(out):
        result, msg = "not_reached", kit_words(out)
    elif refused_notice(out):
        result, msg = "greyed", None
    else:
        result, msg = "looked", None
    lk = {"t": now(), "run": run, "kit": kit_commit(), "by": "crawl", "mode": mode,
          "tab": crumb[0] if crumb and crumb[0] else None, "group": crumb[1] if len(crumb) > 1 else None,
          "path": path, "option": None, "did": "open", "screen": row.get("kind") or None, "result": result,
          "blocker": blocker_of(row.get("notice"), _label_set(camera)) if row.get("notice") else None,
          "fields": [], "kit_message": msg, "records_changed": []}
    looks = [lk]
    for sub in row.get("submenu") or []:
        if isinstance(sub, dict):
            looks += crawl_looks(sub, crumb, mode, run, camera, path)
    return looks


# the prove_run.py arguments under which --skip-settled leaves nothing out: a switched state, a value chosen first, a
# table, a grid, a look, proving again, reading help
SKIP_OFF = (("context", "--context"), ("first", "--first"), ("tables", "--tables"), ("wb", "--wb"),
            ("wb_corners", "--wb-corners"), ("looks", "--looks"), ("look_base", "--look-base"), ("redo", "--redo"),
            ("help_text", "--help-text"))
SKIPPED_KINDS = ("list", "dialog")


def skip_off(a) -> str | None:
    """Why --skip-settled leaves nothing out on a prove_run.py run (SKIP_OFF given), or None."""
    given = [flag for k, flag in SKIP_OFF if getattr(a, k, None)]
    return f"{', '.join(given)} given" if given else None


def prove_filter(todo: list, a, planned=None) -> list:
    """kit/prove_run.py's, before anything connects: what the ledger says of each job, printed in one line (a list or
    dialog job's planned options counted settled one by one: settled(path, option=label)); with --skip-settled, and
    none of SKIP_OFF given, a list or dialog job whose every planned option is settled left out, said so. No other job
    is ever left out. `planned(job)`: the option indices the job proves (proving.jobs.planned). A ledger error leaves
    the jobs as they were."""
    try:
        camera = (paths.camera() or (None,))[0]
        if not camera:
            return todo
        why = []
        led = ledger_for(camera, why)
        if led is None:
            _say(f"no coverage ledger ({'; '.join(why)}): nothing is settled, no row is left out")
            return todo
        skipping = bool(getattr(a, "skip_settled", False))
        off = skip_off(a) if skipping else None
        if off:
            _say(f"--skip-settled leaves nothing out on this run: {off}")
            skipping = False
        mode = _mode_of(getattr(a, "scan", None))
        start = (Path(a.start) if getattr(a, "start", None) else _latest_download(camera)) if skipping else None
        kept = []
        for j in todo:
            path = [str(x) for x in j.get("path") or []]
            v = settled(path, None, mode, camera=camera, start=start, ledger=led, judge=skipping)
            whole, said = False, v.words
            labels = j.get("labels") or []
            if j.get("kind") in SKIPPED_KINDS and labels:
                idx = planned(j) if planned else (j["choose"] if j.get("choose") is not None else range(len(labels)))
                vs = [settled(path, labels[k], mode, camera=camera, start=start, ledger=led, judge=skipping)
                      for k in sorted(idx) if isinstance(k, int) and 0 <= k < len(labels)]
                n = sum(x.skip for x in vs)
                whole = bool(vs) and n == len(vs)
                said = f"{v.words}; {n} of its {len(vs)} planned options settled"
            if skipping and whole:
                _say(f"settled: {said}: left out (--skip-settled)")
                continue
            _say(said + ("; proved all the same (--skip-settled leaves it out)" if whole else ""))
            kept.append(j)
        return kept
    except (Exception, SystemExit) as e:    # noqa: BLE001
        _failed("prove_run.py's gate", e)
        return todo


class ProveLooks:
    """kit/prove_run.py's, after each row: one look from what the row added to proofs.jsonl and failures.jsonl. A row
    proved in a switched state (--context) is said looked at only, and so is a network row that changed nothing (its
    proofs may be the saved option chosen again): neither tells what the row does in general."""

    def __init__(self, run, proofs: Path, fails: Path, network: bool = False, context=None):
        self.camera, self.run = run.root.name, run.dir.name
        self.proofs, self.fails = Path(proofs), Path(fails)
        self.at = {p: (p.stat().st_size if p.exists() else 0) for p in (self.proofs, self.fails)}
        self.private, self.context = network, context

    def _new(self, p: Path) -> list:
        if not p.exists():
            return []
        with open(p, "rb") as f:
            f.seek(self.at[p])
            data = f.read()
        self.at[p] += len(data)
        out = []
        for x in data.decode("utf-8", "replace").splitlines():
            try:
                out.append(json.loads(x))
            except ValueError:
                continue
        return out

    def after(self, job: dict) -> None:
        try:
            proofs, fails = self._new(self.proofs), self._new(self.fails)
            if not proofs and not fails:
                return
            changed = sorted({c.get("key") for p in proofs for c in p.get("changes") or [] if isinstance(c, dict)
                              and RECORD_KEY.match(str(c.get("key")))})
            blocked = next((f for f in fails if f.get("blocked")), None)
            note = None
            if blocked:
                result, blocker, msg = "refused", blocker_of(blocked.get("blocked"), _label_set(self.camera)), None
            elif fails:
                why = fails[-1].get("why")
                result = "kit_failed" if KIT_DETERMINISTIC.match(str(why or "")) else "not_reached"
                blocker, msg = None, kit_words(why)
            else:
                result, blocker, msg = ("changed" if changed else "no_change"), None, None
            if self.context and result in ("changed", "no_change"):
                result, note = "looked", "in a switched state (--context)"
            elif job.get("network_row") and result == "no_change":
                result = "looked"
            append_look(self.camera, {
                "t": now(), "run": self.run, "kit": kit_commit(), "by": "prove", "mode": None,
                "path": [str(x) for x in job.get("path") or []],
                "option": job.get("option") if isinstance(job.get("option"), str) else None, "did": "choose",
                "screen": job.get("kind"), "result": result, "blocker": blocker, "fields": [], "kit_message": msg,
                "records_changed": changed, "note": note}, private=self.private)
        except (Exception, SystemExit) as e:    # noqa: BLE001
            _say(f"the look was not recorded ({type(e).__name__}: {e})")


class NoLooks:
    def after(self, job=None) -> None:
        return None


NO_LOOKS = NoLooks()


def prove_looks(run, proofs: Path, fails: Path, network: bool = False, context=None):
    """kit/prove_run.py's ProveLooks, or NO_LOOKS (said in one line) where it cannot be made: the run goes on."""
    try:
        return ProveLooks(run, proofs, fails, network, context)
    except (Exception, SystemExit) as e:    # noqa: BLE001
        _failed("prove_run.py's looks", e)
        return NO_LOOKS


# ---------------------------------------------------------------- asking it: counts, what is left, one row

def counts(led: Ledger, public: bool = False) -> dict:
    """{"rows": {tab: {status: n}} of the top rows, "deeper": {status: n}, "options": {status: n}, "records":
    {area: {status: [n, value bytes]}}} (area "global", the live records; "set", one memory set's, the sets sharing one
    layout); the record statuses merged as the public form has them with public=True."""
    out = {"rows": {}, "deeper": {}, "options": {}, "records": {"global": {}, "set": {}}}
    for e in led.rows:
        if len(e["path"]) == 1:
            t = out["rows"].setdefault(e["tab"], {})
            t[e["status"]] = t.get(e["status"], 0) + 1
        else:
            out["deeper"][e["status"]] = out["deeper"].get(e["status"], 0) + 1
    for o in led.options:
        for st in o["values"].values():
            out["options"][st] = out["options"].get(st, 0) + 1
    for r in led.records:
        st = PUBLIC_RECORD.get(r["status"], r["status"]) if public else r["status"]
        n = out["records"].setdefault(r["key"].split(":")[0], {}).setdefault(st, [0, 0])
        n[0] += 1
        n[1] += r.get("bytes") or 0
    return out


def needs_of(e: dict) -> str:
    """What the next step on an entry left to do needs (NEEDS): equipment, a kit fix, an owner decision (the opener a
    closed row names), the owner's hand (a row nothing opens, a blocker only the owner's hand changes), a remote proof
    (a row with a setting no proof established, or one a look saw change records no setting maps) or a remote look."""
    st = e.get("status")
    if e.get("changed_in_looks"):
        return "remote-proof"
    if st == "needs equipment":
        return "equipment"
    if st == "kit cannot read":
        return "kit"
    if st == "closed by rule":
        return "hand" if (e.get("opener") or ["never"]) == ["never"] or e.get("never_choose") else "decision"
    if st == "greyed in state":
        return "hand" if (e.get("blocker") or {}).get("remote") else "remote-look"
    return "remote-proof" if e.get("settings") or e.get("tied") or e.get("through") else "remote-look"


NEXT = {"remote-look": "open it remotely and read what it shows (kit/drive.py --path ... --press right)",
        "remote-proof": "prove its options remotely (kit/prove_run.py --rows ...), or name what a look saw change",
        "hand": "by the owner's hand, a camera download before and after (kit/tools/coverage.py --record)",
        "equipment": "attach the equipment named, then look again remotely",
        "decision": "a dated owner decision naming the row (the opener), then a remote look",
        "kit": "mend the kit (its message is in the private form), then look again"}
COST = {"remote-look": 1, "remote-proof": 2, "kit": 2, "equipment": 3, "decision": 3, "hand": 4}


def _neighbours(led: Ledger) -> dict:
    """{id(top row entry): [unmapped record keys]} of each row whose records are the nearest mapped ones below or
    above an unmapped record (in the file's id order, each area apart): a lead, never a proof."""
    on = {}
    for e in led.rows:
        if len(e["path"]) == 1:
            for k in _row_settings(led, e):
                on.setdefault(record_base(k), e)
    out = {}
    for area in ("global", "set"):
        recs = [r for r in led.records if r["key"].startswith(area + ":")]
        mapped = [i for i, r in enumerate(recs) if r["key"] in on]
        for i, r in enumerate(recs):
            if not r["status"].startswith(("unmapped", "changed")):
                continue
            below = max((j for j in mapped if j < i), default=None)
            above = min((j for j in mapped if j > i), default=None)
            for j in (below, above):
                if j is not None:
                    out.setdefault(id(on[recs[j]["key"]]), []).append(r["key"])
    return out


def held_values(led: Ledger, e: dict) -> tuple:
    """(values still to try, values inferred from a shared list) of the settings a row holds itself: placed on that very
    row, or tied to it, never those of a row below it nor those a proof drew through it, whose own rows count them
    (values_left counts them all: a row with any value left below it is never settled)."""
    if getattr(led, "_own_index", None) is None:
        led._own_index = ({o["key"]: o for o in led.options},
                          {s["key"]: s for s in led.src.definition.get("settings") or []})
    opts, by_key = led._own_index
    keys = [k for k in e["settings"] if (by_key.get(k) or {}).get("row") == e["path"]] + e["tied"]
    sts = [st for k in dict.fromkeys(keys) for st in (opts.get(k) or {}).get("values", {}).values()]
    return sum(1 for st in sts if st in LEFT), sts.count(INFERRED)


def todo(led: Ledger, tab: str = None, mode: str = None, needs: str = None) -> list:
    """What is left ([{entry, needs, next, yield, near, left, inferred}]): the rows in TODO statuses, the rows holding
    values still to try themselves (held_values: each value counted once, on the row its setting is placed on, "left";
    "inferred" beside it, whatever the row's own status) and those a look saw change records no setting maps, filtered
    by tab, mode and what the next step needs, sorted by expected yield: the unmapped records next to the row (weighted
    by how the leads class them: a record seen to change counts three), the records a look saw change, whether the row
    has settings, less the cost of the step."""
    near = _neighbours(led)
    leads = {}
    for part in ("live", "sets"):
        for x in (led.src.leads or {}).get(part) or []:
            if isinstance(x, dict) and record_base(x.get("key")):
                leads[record_base(x["key"])] = x.get("cls")
    status_of = {r["key"]: r["status"] for r in led.records}
    out = []
    for e in led.rows:
        left, inferred = held_values(led, e)
        if e["status"] not in TODO and not e.get("changed_in_looks") and not left:
            continue
        if tab and plain(e["tab"]) != plain(tab):
            continue
        if mode and plain(e["mode"]) != plain(mode):
            continue
        n = needs_of(e)
        if needs and n != needs:
            continue
        recs = near.get(id(e), []) if len(e["path"]) == 1 else []
        weight = sum(3 if (leads.get(k) not in (None, "NEVER") or status_of.get(k) == "changed, no row attributed")
                     else 1 for k in recs)
        y = weight + 5 * len(e.get("changed_in_looks") or []) + \
            (2 if e.get("settings") or e.get("tied") or e.get("through") else 0) - COST[n]
        out.append({"entry": e, "needs": n, "next": NEXT[n], "yield": y, "near": recs, "left": left,
                    "inferred": inferred})
    out.sort(key=lambda x: (-x["yield"], x["entry"]["order"], [plain(p) for p in x["entry"]["path"]]))
    return out


def row_view(led: Ledger, label: str, public: bool = False) -> list:
    """The lines kit/tools/coverage.py --row prints for every entry whose last label is `label`: its place, status,
    class and opener, blocker, equipment, field names, settings, and (unless public) its citations: runs and looks."""
    out = []
    for e in led.rows:
        if not same_label(e["path"][-1], label):
            continue
        out.append(f"{e['mode']} > {e['tab']} > {e['group']} > {' > '.join(e['path'])}: {e['status']}"
                   + (f" (as the first {e['path'][0]!r}, in {e['same_label_as']})" if e.get("same_label_as") else ""))
        if e.get("rule"):
            out.append(f"   rule: {e['rule']}; opens with {', '.join(e.get('opener') or [])}"
                       + ("; no option is ever chosen" if e.get("never_choose") else ""))
        for k in ("blocker", "equipment", "fields", "reason", "placement_missing", "inferred", "values_left",
                  "values_inferred"):
            if e.get(k):
                out.append(f"   {k}: {e[k]}")
        if e.get("confirmed"):
            out.append("   confirmed: a look or a hand check showed no record differ")
        keys = _row_settings(led, e)
        if keys:
            out.append(f"   settings: {len(keys)} ({', '.join(keys[:6])}{' ...' if len(keys) > 6 else ''})")
        if public:
            continue
        for c in e.get("cites") or []:
            out.append("   cites: " + ", ".join(f"{k} {v}" for k, v in c.items() if v not in (None, [], "")))
        if e.get("kit_message"):
            out.append(f"   the kit's message: {e['kit_message']}")
        if e.get("changed_in_looks"):
            out.append(f"   a look saw these records change: {', '.join(e['changed_in_looks'])}")
        if e.get("looked"):
            out.append(f"   looked at {e['looked']} time(s)" + (f"; options seen {e['options_seen']}"
                                                                if e.get("options_seen") else ""))
        if e.get("proofs"):
            out.append(f"   proofs: {e['proofs']}")
    return out


# ---------------------------------------------------------------- the evidence each valid proof rests on

def bundles_report(led: Ledger) -> list:
    """Per run folder ({"run", "frames": [backing, not, bytes backing, bytes not], "downloads": [...]}): which of its
    frames (shots/) and downloads (dat/) back a valid proof's bundle and which do not. Nothing is deleted: the basis
    for a later decision of the owner's."""
    root = led.src.run_root
    if root is None or not root.is_dir():
        return []
    back = {}
    for b in led.bundles:
        s = back.setdefault(b["run"], set())
        s |= set(b.get("frames") or [])
        s |= {x.get("file") for x in (b.get("before") or {}, b.get("after") or {}) if x.get("file")}
    out = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        row = {"run": d.name}
        for kind, sub, pat in (("frames", "shots", "*.png"), ("downloads", "dat", "*.DAT")):
            n = [0, 0, 0, 0]
            for f in (d / sub).glob(pat) if (d / sub).is_dir() else []:
                i = 0 if f.name in back.get(d.name, set()) else 1
                n[i] += 1
                n[2 + i] += f.stat().st_size
            row[kind] = n
        if any(row["frames"]) or any(row["downloads"]):
            out.append(row)
    return out
