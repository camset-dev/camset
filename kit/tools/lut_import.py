"""Import one user LUT into the camera, and print which records of its settings file that changed: the evidence for the
camera's Manage User LUTs rows (Movie > Exposure/Color > Color/Tone), by Sony's documented ImportLUTFile, only as
docs/decisions/0026 allows: a .cube file from the clone's own private/lut/, into user place 16, and only where the
camera's own Import/Edit table was seen to show it empty since the last import, on the owner's word for the run, which
the run carries as --allow "Manage User LUTs".

    .venv/bin/python -u kit/tools/lut_import.py private/lut/<pack>/<name>.cube --allow "Manage User LUTs" \\
        --seen-empty <run>/shots/<frame>.png [--run kit2_lut]

One session, as every run of the kit has (docs/decisions/0015): the link, the camera's own picture of its screen (OSD)
as its eyes, no reader, and no key pressed nor anything answered on the camera's screen.
 1. Before anything connects. Without --allow "Manage User LUTs", the owner's word, it stops, as a prover does without
    its row's allowance; the allowance goes into the run's events.jsonl and lut_import.jsonl. The file is checked
    (camkit.link.lut_refused): a .cube file under the clone's own private/lut/ (where its path really ends, never
    through a link), a name Sony's reference takes, under 3,000,000 bytes, a .cube LUT's text. And place 16's emptiness,
    which no camera property tells (DeleteUserBaseLook lists every place, held or empty: kit/common/lut_file.h): the
    frame --seen-empty names is a look at the camera's own Manage User LUTs > Import/Edit table (seen_empty): under this
    camera's runs, in a run's shots/, never a link; its run's drive.jsonl records that path and the frame with the
    screen's text the kit's OCR read at the look, its events.jsonl when it was taken; that text begins with the title
    "Import/Edit" and reads User16's own row "User16: (No Import)" (the row for 16, not User1's nor User160's, spaces and
    a dropped colon as OCR gives them; a row runs to the next "UserN"); taken after the
    last import the SDK was asked for (any run's lut_import.jsonl) and at most LOOK_LIMIT (an hour) before now, on the
    same day. Its path, SHA-256 and row as read go into events.jsonl ("lut_seen_empty") and lut_import.jsonl. The look
    is made with kit/drive.py (look_command, which the tool prints when it refuses one), the camera in Movie: Right on
    Import/Edit, Down to User16, MENU; nothing chosen. Any of this refused: said, with the command, nothing sent.
 2. The start file is downloaded first, and the menu's lock after it waited out (camkit.session.wait_lock: LOCK_S, as
    there is no HDMI picture to watch). The camera saves its settings only on the shooting screen with a card in: a
    refused download is said, and the run ends there, nothing changed.
 3. BaseLookImportOperationEnableStatus is read and printed. Where it does not read Enable (1), or cannot be read,
    that is said with what the camera reads, and nothing is imported (Sony's reference allows the import only while it
    reads Enable; the camera may give it in Movie mode).
 4. The import (camkit.link.Link.import_lut: camlink's importlut, which checks the file again against the clone's
    folder it was built with, reads the camera's recording state and its list of user places, then gives ImportLUTFile
    a copy of the bytes it checked and waits for the camera's answer). Only the camera's
    ImportLUTFile_Result_OK is an import; a refusal is said as that. Where the answer did not come (camlink's
    "import_unconfirmed": the import may still be running) nothing more is sent, no download and no upload, which
    would restart the camera mid-import: RESTORE_BY_HAND is written naming the start file, the owner is told to look
    at Manage User LUTs on the camera, and the run ends with status 5 once the camera shows its shooting screen.
 5. The end every run has, whatever happened above, as runner.prover_session's: the camera's own picture of its screen,
    kept in the run's shots and read (camkit.screen), its kind printed; where it does not read as the shooting screen
    nothing is downloaded or uploaded, and the run holds as runner.end_session holds (runner.hold_for_owner:
    RESTORE_BY_HAND, the link kept open, the owner asked to clear the screen, status 5). Then camkit.session.ended (a
    download, the camera's word on Playback asked first) and every record that differs from the start file, by key,
    with the setting the camera's definition names on it and its values: the mapping's evidence of what the file holds
    of a user LUT (values a camera holds stay in the run, docs/decisions/0016); then camkit.session.put_back, the start
    file uploaded when anything differs, and camkit.session.verify_restore after the restart, the import's records
    said by key and left out of its count when the camera confirmed the import. A record that did not go back fails
    the restore (status 4), each named, to be looked at on the camera, unless it is one camkit.not_by_file.USER_LUT
    names as holding a user LUT (none yet: the first import's run names them). These steps are session.finish's two
    halves, taken apart so the records are listed with their names between; not runner.end_session, whose way to the
    shooting screen presses MENU and whose fallback restores over a menu or a list.
 6. Once the camera took the LUT, the two kit/tools/coverage.py --record commands that keep the finding in the
    coverage ledger, for Manage User LUTs and its Import/Edit (Movie, Exposure/Color > Color/Tone), with this run's
    start download and the one after the import: run them as printed, once the output reads right. They write one look
    each into the looks file (private/evidence/<model>_fw<fw>/, the mapper's own), the records that changed by key
    alone, never a value: --did act when records changed, which the ledger counts as a hand check that changed a record
    ("proved by hand"; its public form says only that the row changed a record), --did choose when none did ("tested,
    no record changes", private). The looks file's "by" says "hand", the one its vocabulary has for a change made
    outside the kit's walks; the note says it was this tool. No proof line is written: a proof's values would reach the
    definition, and a LUT's records may hold its name (docs/decisions/0016). And the same look at the Import/Edit table
    again (look_command), so that the row for 16 is on record with its new reading; the tool presses nothing itself.
The LUT stays in user place 16 until the owner deletes it on the camera by hand (Manage User LUTs); the kit deletes
nothing.

Exit status (kit/exit_status.py): 0 when the camera took the LUT and the restore checked out, or a STOP came before the
import (nothing imported, said); 8 (EXIT_INCOMPLETE) when nothing was imported, or its answer did not come back at all,
and the camera is on its start file again; 7 (EXIT_REFUSED) when the kit's guards refused the import at the line; 5
(EXIT_RESTORE_BY_HAND) when the import was not confirmed, or the end found a screen no restore may go over, or the
camera was in Playback: put the start file back with kit/tools/upload_check.py, as RESTORE_BY_HAND names it; 4
(EXIT_UNRESTORED) when the start file could not be put back or a record did not go back; 1 when nothing was sent at
all (no allowance, the file or the look refused, no link, the start download refused).
"""
import argparse
import datetime
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, camset, definitions, jsonl, paths, provenance, safety, screen, session  # noqa: E402
from camkit.frames import OsdFeed  # noqa: E402
from camkit.link import LUT_OK, LUT_PLACE, Link, LinkError, LutNotImported, StopRequested, lut_refused  # noqa: E402
from camkit.not_by_file import USER_LUT  # noqa: E402
from camkit.runs import Run, mark_restore_by_hand  # noqa: E402
from camkit.session import Ending, compared, verify_restore, wait_lock  # noqa: E402
from exit_status import EXIT_INCOMPLETE, EXIT_REFUSED, EXIT_RESTORE_BY_HAND, EXIT_UNRESTORED  # noqa: E402
from runner import add_allow_argument, allowed_or_exit, hold_for_owner  # noqa: E402

ALLOW_ROW = "Manage User LUTs"   # the row the owner's word names (--allow), as decision 26 has it
ENABLE_PROPERTY = "BaseLookImportOperationEnableStatus"
ENABLE = 1                       # CrBaseLookImportOperation_Enable (kit/common/lut_file.h kEnable)
STATUS_WORDS = {0: "Disable", 1: "Enable"}
TRIES, PAUSE = 4, 10.0           # the download at the end, as camkit.session.ended tries a session's last one
ELEMENTS_SAID = 32               # the most elements of one array record said
WHERE = "Movie > Exposure/Color > Color/Tone > Manage User LUTs"
UNCONFIRMED = "import_unconfirmed"      # camlink's cause when the camera's answer did not come (kit/common/lut_file.h)

# The look that says place 16 is empty (seen_empty): the camera's own table, seen through kit/drive.py
LOOK_PATH = ["Manage User LUTs", "Import/Edit"]
LOOK_TITLE = "import/edit"              # the table's title, first in the screen's text (no spaces, lower case)
LOOK_LIMIT = 3600.0                     # s: the oldest a look may be when the import starts (and on the same day)
LOOK_SKEW = 60.0                        # s: a look this far ahead of the clock is taken as now; any further, refused
LOOK_DOWNS = 15                         # Down presses from User1 to User16 in the table
# The screen's text as kit/drive.py keeps it: every line the kit's OCR read, in reading order, joined by spaces
# ("Import/Edit User LUT Input AE Level Offset User11: (No Import) ... User16: (No Import) MENU", kit2_fin_lut_table
# 00034_down.png). A row runs from its "UserN" to the next one, or to the end, the footer's MENU after the last row
ROW_START = re.compile(r"user\s*(\d+)\s*[:;]?", re.I)
EMPTY_ROW = re.compile(r"user\s*16\s*[:;]?\s*\(\s*no\s*import\s*\)", re.I)     # User16's row, read empty


class NotSeenEmpty(Exception):
    """seen_empty's refusal: why the frame does not establish that place 16 is empty."""


def say(m: str) -> None:
    print(m, flush=True)


def look_command(root: Path | None = None) -> str:
    """The kit/drive.py command that makes the look --seen-empty takes, as the camera's operator runs it (the camera in
    Movie, its OSD eyes): Right on Import/Edit, Down to User16, MENU; nothing chosen. Its --scan is the camera's latest
    Movie page scan made with OSD eyes (runner.latest_scan, Intelligent Auto's first), or a placeholder."""
    scan = None
    try:
        from runner import latest_scan
        scan = latest_scan("Movie", root, auto=True, eyes="osd") or latest_scan("Movie", root, eyes="osd")
    except Exception:           # noqa: BLE001 (a placeholder says what to put there)
        scan = None
    words = [".venv/bin/python", "-u", "kit/drive.py", "--scan", scan.name if scan else "<a Movie page scan, OSD eyes>",
             "--run", "kit2_lut_look", "--note", "the user LUT table: is User16 empty; nothing chosen",
             "--path", LOOK_PATH[0], "--path", LOOK_PATH[1], "--press", "right"]
    words += ["--press", "down"] * LOOK_DOWNS + ["--press", "menu"]
    return "CAMSET_EYES=osd " + shlex.join(words)


def _local_time(text) -> float | None:
    try:
        return datetime.datetime.fromisoformat(str(text)).timestamp()
    except ValueError:
        return None


def last_import_asked(root: Path) -> float | None:
    """When the SDK was last asked to import a LUT on this camera, by any run (each run's lut_import.jsonl: asked_at, or
    a line's own t where it is from before that field and says it was called or confirmed), whatever the camera
    answered; None when none was asked."""
    times = []
    for f in sorted(Path(root).glob("*/lut_import.jsonl")):
        try:
            lines = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
        except (OSError, ValueError):
            continue
        for x in lines:
            if not isinstance(x, dict):
                continue
            if isinstance(x.get("asked_at"), (int, float)):
                times.append(float(x["asked_at"]))
            elif x.get("called") is True or x.get("confirmed") is True or x.get("result") == LUT_OK:
                t = _local_time(x.get("t"))
                if t is not None:
                    times.append(t)
    return max(times) if times else None


def _flat(text) -> str:
    return re.sub(r"\s+", "", str(text or "")).lower()


def rows_16(text: str) -> list:
    """User16's rows in a screen's text as kit/drive.py keeps it: from each "User16" (spaces and a colon as OCR gives
    them; never User1's, nor User160's) to the next row's "UserN", or the end."""
    starts = list(ROW_START.finditer(text or ""))
    return [text[m.start():(starts[i + 1].start() if i + 1 < len(starts) else len(text))].strip()
            for i, m in enumerate(starts) if m.group(1) == "16"]


def seen_empty(given, root: Path, now: float, last_asked: float | None) -> dict:
    """That the frame `given` (a path, or one relative to `root`, the camera's run root) shows place 16 empty on the
    camera's own Import/Edit table, seen after the last import asked (`last_asked`) and at most LOOK_LIMIT before `now`,
    on the same day: {"frame": its path from the run root, "sha256", "row": User16's row as the kit's OCR read it,
    "look_t": when the look's run says it was taken, "look_run"}. Raises NotSeenEmpty, saying why, otherwise.
    The screen's text is the one kit/drive.py kept for the frame in its drive.jsonl: the kit's OCR's reading of the
    whole screen at the look (camkit.live.text_of), never read again here, since a new module reads the screen neither
    by itself nor yet through camkit.reading.read (docs/decisions/0022; kit/tests/test_reading.py holds both gates)."""
    root = Path(root)
    p = Path(given)
    if not p.exists() and not p.is_absolute():
        p = root / p
    if p.is_symlink():
        raise NotSeenEmpty(f"{p} is a link: name the frame itself")
    try:
        real, top = p.resolve(strict=True), root.resolve(strict=True)
    except (OSError, RuntimeError):
        raise NotSeenEmpty(f"{p} is not there") from None
    if not real.is_relative_to(top):
        raise NotSeenEmpty(f"{p} is not under this camera's runs ({paths.shown(top)}/)")
    if real.parent.name != "shots" or real.parent.parent.parent != top:
        raise NotSeenEmpty(f"{p} is not in a run's shots/ folder, where kit/drive.py keeps a look's frames")
    if real.suffix.lower() != ".png" or not real.is_file():
        raise NotSeenEmpty(f"{p} is not a .png frame")
    run_dir, name = real.parent.parent, real.name
    looked = None
    try:
        for x in (run_dir / "events.jsonl").read_text(encoding="utf-8").splitlines():
            e = json.loads(x) if x.strip() else {}
            if isinstance(e, dict) and e.get("frame") == name and isinstance(e.get("t"), (int, float)):
                looked = float(e["t"])
    except (OSError, ValueError):
        looked = None
    if looked is None:
        raise NotSeenEmpty(f"{run_dir.name}'s events.jsonl does not say when {name} was taken")
    text = None
    try:
        for x in (run_dir / "drive.jsonl").read_text(encoding="utf-8").splitlines():
            d = json.loads(x) if x.strip() else {}
            if isinstance(d, dict) and d.get("path") == LOOK_PATH:
                for s in d.get("screens") or []:
                    if isinstance(s, dict) and s.get("frame") == name:
                        text = s.get("text") if isinstance(s.get("text"), str) else ""
    except (OSError, ValueError):
        text = None
    if text is None:
        raise NotSeenEmpty(f"{run_dir.name}'s drive.jsonl does not record {name} on a look at "
                           f"{' > '.join(LOOK_PATH)}")
    if looked > now + LOOK_SKEW:
        raise NotSeenEmpty(f"{name} was taken {looked - now:.0f} s ahead of this computer's clock")
    if now - looked > LOOK_LIMIT:
        raise NotSeenEmpty(f"{name} was taken {(now - looked) / 60:.0f} minutes ago, more than an hour before this "
                           "import: look at the table again")
    if time.localtime(looked)[:3] != time.localtime(now)[:3]:
        raise NotSeenEmpty(f"{name} was taken on another day: look at the table again")
    if last_asked is not None and looked <= last_asked:
        raise NotSeenEmpty(f"{name} was taken before the last import the camera was asked for "
                           f"({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_asked))}); a look after the last "
                           "import is needed")
    if not text.strip():
        raise NotSeenEmpty(f"{run_dir.name}'s drive.jsonl kept no text for {name} (a run that withholds the screen's "
                           "text, or one that read none): look at the table again with the command below")
    if not _flat(text).startswith(LOOK_TITLE):
        raise NotSeenEmpty(f"{name} does not read as the Import/Edit table (its text begins {text[:40]!r})")
    sixteen = rows_16(text)
    if not sixteen:
        raise NotSeenEmpty(f"User16's row is not on this frame ({name}): look down to User16 and name that frame")
    empty = EMPTY_ROW.match(sixteen[0])
    if len(sixteen) > 1 or not empty:
        raise NotSeenEmpty(f"User16 reads {' / '.join(sixteen)!r} on {name}, not \"User16: (No Import)\": place 16 is "
                           "not seen empty")
    row = empty.group(0)
    return {"frame": real.relative_to(top).as_posix(), "sha256": provenance.sha256(real), "row": row,
            "look_t": round(looked, 3), "look_run": run_dir.name}


def allowed(allow) -> str:
    """The allowance's words for the run's logs: exits before anything connects unless --allow names Manage User LUTs,
    the owner's word for the run, and nothing else (runner.allowed_or_exit then says it and gives its words)."""
    if not safety.named(ALLOW_ROW, allow):
        sys.exit(f"lut_import: a user LUT reaches the camera only on the owner's word for the run "
                 f"(docs/decisions/0026): --allow {ALLOW_ROW!r}")
    others = [x for x in allow if not safety.named(ALLOW_ROW, [x])]
    if others:
        sys.exit(f"lut_import: --allow names {others}: this run takes no allowance but {ALLOW_ROW!r}")
    return allowed_or_exit(allow)


def given_path(text: str) -> Path:
    """The LUT as the command line names it: as given when it is there, else from the clone's root."""
    p = Path(text).expanduser()
    return p if p.exists() or p.is_absolute() else ROOT / p


def enable_status(link) -> tuple:
    """(BaseLookImportOperationEnableStatus's value, how it reads in words): (None, why) when it cannot be read."""
    try:
        v = link.get(ENABLE_PROPERTY).get("current")
    except LinkError as e:
        return None, f"could not be read ({e})"
    if not isinstance(v, int) or isinstance(v, bool):
        return None, f"could not be read (camlink gave {v!r})"
    return v, f"reads {v}" + (f" ({STATUS_WORDS[v]})" if v in STATUS_WORDS else "")


def setting_names() -> dict:
    """{key: name} of the settings of the camera the kit works on (its definition), or {} while it has none."""
    try:
        p = definitions.active(required=False)
        return {s["key"]: s["name"] for s in definitions.load(p)["settings"]} if p and p.exists() else {}
    except Exception:           # noqa: BLE001 (names are a help to read the records by, never needed)
        return {}


def change_line(c, names: dict) -> str:
    """One record that differs: its key, the setting the definition names on it (or none yet), its values."""
    name = names.get(c.key) or names.get("set:" + c.key.split(":")[1]) or "no setting named on it yet"
    if isinstance(c.before, list) and isinstance(c.after, list) and len(c.before) == len(c.after):
        idx = [i for i, (x, y) in enumerate(zip(c.before, c.after, strict=True)) if x != y]
        more = f" ... ({len(idx) - ELEMENTS_SAID} more)" if len(idx) > ELEMENTS_SAID else ""
        return (f"   {c.key} ({name}) [{len(idx)} of {len(c.before)} elements differ] " +
                ", ".join(f"[{i}] {c.before[i]!r} -> {c.after[i]!r}" for i in idx[:ELEMENTS_SAID]) + more)
    return f"   {c.key} ({name}): {c.before!r} -> {c.after!r}"


LEDGER_ROWS = ("Exposure/Color > Color/Tone > Manage User LUTs > Import/Edit", "Exposure/Color > Color/Tone > Manage User LUTs")
NOTE = "a user LUT imported through Sony's ImportLUTFile by kit/tools/lut_import.py, not by hand (docs/decisions/0026)"


def record_commands(start: Path, after: Path, place: int, changed: bool) -> list:
    """The kit/tools/coverage.py --record commands that keep this run's finding in the coverage ledger (the module
    docstring's step 6): one for Import/Edit, with the place as its option (User<place>, as the camera's table names
    it), one for Manage User LUTs; --did act when records changed, choose when none did."""
    windows = os.name == "nt"
    out = []
    for row in LEDGER_ROWS:
        words = [".venv\\Scripts\\python" if windows else ".venv/bin/python", "kit/tools/coverage.py", "--record",
                 "--mode", "Movie", "--path", row, "--did", "act" if changed else "choose"]
        if row.endswith("Import/Edit"):
            words += ["--option", f"User{place}"]
        words += ["--start", paths.shown(start), "--end", paths.shown(after), "--note", NOTE]
        out.append(subprocess.list2cmdline(words) if windows else shlex.join(words))
    return out


def newest(run, tag: str) -> Path | None:
    """The run's latest download of that tag (their numbers rise: 00007_restored.DAT after 00003_restored.DAT)."""
    got = sorted(run.dat.glob(f"*_{tag}.DAT"))
    return got[-1] if got else None


def screen_kind(link, eyes, tag: str = "end-check") -> str | None:
    """The kind of the screen the camera shows now, from its own picture (the OSD eyes' grab, kept in the run's shots
    under `tag`), as camkit.session.kind_seen reads it (the playback view told from the shooting screen by the
    camera's word); None when the picture cannot be had or read. Printed either way."""
    try:
        f = eyes.grab(tag)
        kind = session.kind_seen(link, f, screen.read(f))
    except Exception as e:      # noqa: BLE001 (a picture that cannot be had is a screen no restore goes over)
        say(f"the camera's screen could not be looked at ({type(e).__name__}: {e})")
        return None
    say(f"the camera's screen: {kind}")
    return kind


def held(link, eyes, start: Path, kind) -> None:
    """Where the screen before the end is not the shooting screen: nothing downloaded or uploaded, the run holding for
    the owner as runner.end_session does (runner.hold_for_owner; it exits EXIT_RESTORE_BY_HAND)."""
    why = (session.PLAYBACK_HELD if kind == session.PLAYBACK else
           f"its own picture reads as {kind!r}, not the shooting screen" if kind else
           "its own picture could not be had or read")
    hold_for_owner(link, eyes, start, why)


def importing(link, lut: Path, out: dict) -> dict:
    """The enable status, then the import: what happened ({"code", "called", "confirmed", "unconfirmed"}). Whatever is
    raised here is said and ends it, so the session's end runs all the same (runner.prover_session's way)."""
    got = {"code": 0, "called": False, "confirmed": False, "unconfirmed": False}
    try:
        status, words = enable_status(link)
        out["enable_status"] = status
        say(f"{ENABLE_PROPERTY} {words}")
        if status != ENABLE:
            say(f"the camera does not allow a LUT import now: {ENABLE_PROPERTY} {words}, and Sony's reference allows "
                f"the import only while it reads Enable ({ENABLE}); nothing was imported. The camera may give it in "
                "Movie mode: switch to Movie, then run this again")
            got["code"] = EXIT_INCOMPLETE
            return got
        got["called"] = True                    # from here the camera may change, until an answer says otherwise
        out["asked_at"] = round(time.time(), 3)     # a look must come after it (last_import_asked)
        try:
            r = link.import_lut(lut)
        except LutNotImported as e:
            got["called"] = e.called
            out["result"] = e.reply.get("result") or e.reply.get("cause")
            say(f"no import confirmed: {e}")
            got["unconfirmed"] = e.reply.get("cause") == UNCONFIRMED
            got["code"] = EXIT_INCOMPLETE
        except safety.Refused as e:
            got["called"] = False
            say(f"the kit's guards refused the import ({e}); nothing was imported")
            got["code"] = EXIT_REFUSED
        except StopRequested as e:
            got["called"] = False
            say(f"a STOP was asked for before the import ({e}); nothing was imported")
        except LinkError as e:
            # no answer at all (camlink gone, the link in a network error): whether the SDK was asked is not known, so
            # the camera is taken as changed
            say(f"the import's answer did not come ({e}): whether the LUT went in is not known; the camera's settings "
                "are downloaded and compared all the same")
            got["code"] = EXIT_INCOMPLETE
        else:
            got["confirmed"] = True
            out["imported_at"] = round(time.time(), 3)
            out["result"] = r.get("result")
            say(f"{LUT_OK}: {out['file']} is in user place {LUT_PLACE} (the camera answered in {r.get('ms')} ms)")
    except Exception as e:      # noqa: BLE001 (the end runs whatever is raised, as prover_session's does)
        say(f"stopped: {type(e).__name__}: {e}")
        got["code"] = EXIT_INCOMPLETE
    return got


def unconfirmed_end(link, eyes, run, start: Path) -> int:
    """The camera's answer did not come: no download and no upload (an upload restarts the camera, maybe mid-import);
    RESTORE_BY_HAND for the start file (camkit.runs: no link opens until kit/tools/upload_check.py has put it back), the
    owner told what to look at, and the link closed only over the shooting screen (else held for the owner)."""
    marker = mark_restore_by_hand(run.root, run.dir.name, start,
                                  "the LUT import was not confirmed: the camera may still have been importing")
    run.log("lut_unconfirmed_held", marker=str(marker))
    try:
        shown = Path(start).relative_to(run.root).as_posix()
    except ValueError:
        shown = str(start)
    say(f"nothing more is sent: an upload would restart the camera while it may still be importing. Look at {WHERE} > "
        f"Import/Edit on the camera: whether User{LUT_PLACE} holds the LUT. Then put the start file back with\n"
        f"  .venv/bin/python -u kit/tools/upload_check.py {shown}\n({marker} names it; docs/decisions/0015)")
    kind = screen_kind(link, eyes)
    if kind != "shooting":
        held(link, eyes, start, kind)
    return EXIT_RESTORE_BY_HAND


def ending(link, eyes, start: Path, called: bool, confirmed: bool) -> Ending:
    """The session's end over the shooting screen alone (held otherwise): session.ended, the records listed, then
    session.put_back."""
    kind = screen_kind(link, eyes)
    if kind != "shooting":
        held(link, eyes, start, kind)
    end = session.ended(link, start, "after-lut" if called else "after", tries=TRIES, pause=PAUSE, show=0, say=say)
    if end.after is None:
        return end
    if confirmed and end.changes:
        say("as the import left them:")
    names = setting_names()
    for c in end.changes:
        say(change_line(c, names))
    return session.put_back(link, end, start, say=say)


def checked_restore(run, start: Path, keys: list, confirmed: bool) -> int | None:
    """After the upload: verify_restore (the import's records said by key and left out of its count when the camera
    confirmed the import), then every record still differing from the start file named; None when it checks out, else
    EXIT_UNRESTORED. Only a record camkit.not_by_file.USER_LUT names for the camera's model may stay, and only after a
    confirmed import."""
    n = verify_restore(run, start, expected=frozenset(keys) if confirmed else frozenset(), say=say)
    if n is None:
        say("the restore could not be checked: the camera did not answer after its restart. Check that it is on and "
            f"connected, then run kit/tools/upload_check.py {start}")
        return EXIT_UNRESTORED
    restored = newest(run, "restored")
    left = [c.key for c in compared(start, restored, say=lambda m: None)] if restored is not None else []
    model = camset.read(start).model
    known = set(USER_LUT.get(model, ())) if confirmed else set()
    unexplained = [k for k in left if k not in known]
    if unexplained:
        say(f"the restore did not check out: {len(unexplained)} records did not go back to the start file: "
            f"{', '.join(unexplained)}. Look at these settings on the camera"
            + (", and at the records the import changed: none is known yet to hold a user LUT "
               "(camkit.not_by_file.USER_LUT names none for this camera), so none may stay" if confirmed else "")
            + f"; then run kit/tools/upload_check.py {start}")
        return EXIT_UNRESTORED
    if left:
        say(f"{len(left)} records did not go back, each one camkit.not_by_file.USER_LUT names as holding a user LUT: "
            f"{', '.join(left)}")
    else:
        say(f"the restore put back every record that differed ({len(keys)})")
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("file", help="the .cube file, under the clone's own private/lut/")
    add_allow_argument(ap)
    ap.add_argument("--seen-empty", required=True, metavar="FRAME",
                    help="a frame of a look at the camera's own Manage User LUTs > Import/Edit table (kit/drive.py, the "
                         "camera in Movie) on which User16's row reads \"(No Import)\", taken since the last import and "
                         "at most an hour ago: a path, or one in the camera's runs (kit2_lut_look/shots/00034_down.png)")
    ap.add_argument("--run", default="kit2_lut", help="the run folder, in the camera's runs/<model>_fw<fw>/")
    a = ap.parse_args()
    allowance = allowed(a.allow)
    lut = given_path(a.file)
    why = lut_refused(lut)
    if why:
        say(f"nothing was sent: {why}")
        return 1
    root = paths.run_root()
    try:
        seen = seen_empty(a.seen_empty, root, time.time(), last_import_asked(root))
    except NotSeenEmpty as e:
        say(f"nothing was sent: place 16 is not seen empty: {e}. Decision 26 imports only where the camera's own "
            f"Import/Edit table was seen to show it empty since the last import. With the camera in Movie, look at it "
            f"(nothing is chosen) and name the frame that shows User16 with --seen-empty:\n  {look_command(root)}")
        return 1
    say(f"place 16 seen empty: {seen['row']!r} on {seen['frame']}")
    run = Run(a.run)
    run.log("lut_allowance", allow=list(a.allow), allowance=allowance)
    run.log("lut_seen_empty", **seen)
    out = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "file": lut.resolve().name, "sha256": provenance.sha256(lut),
           "place": LUT_PLACE, "allowance": allowance, "seen_empty": seen}
    code = 1
    try:
        code = session_run(run, lut, out)
        return code
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
        raise
    finally:
        out["exit"] = code
        jsonl.append(run.dir / "lut_import.jsonl", out)


def session_run(run, lut: Path, out: dict) -> int:
    """The session (the module docstring's steps 2 to 6); its exit status. `out` gathers lut_import.jsonl's line."""
    eyes = OsdFeed(run)
    start, end, got, code = None, None, None, 1
    try:
        with Link(run) as link:
            eyes.attach(link)
            try:
                start = link.download("start")
            except LinkError as e:
                say(f"the camera refused the start download ({e}): it saves its settings only on the shooting screen, "
                    "with a card in. Close any menu on the camera by hand and run this again; nothing was imported")
                return 1
            since = time.monotonic()
            out["start"] = start.name
            say(f"start file: {start.name}")
            wait_lock(since, None)
            got = importing(link, lut, out)
            code = got["code"]
            out.update(called=got["called"], confirmed=got["confirmed"])
            if got["unconfirmed"]:
                return unconfirmed_end(link, eyes, run, start)
            end = ending(link, eyes, start, got["called"], got["confirmed"])
    except LinkError as e:
        if start is None:
            say(f"no link to the camera ({e}); nothing was sent")
            return 1
        say(f"the session ended early ({e}): the start file may not be on the camera; put it back with "
            f"kit/tools/upload_check.py {start}")
        return EXIT_UNRESTORED
    finally:
        eyes.close()
    if end is None or end.after is None:
        return EXIT_UNRESTORED          # session.ended said how the start file goes back
    keys = [c.key for c in end.changes]
    out.update(after=end.after.name, records_changed=keys)
    if end.uploaded:
        failed = checked_restore(run, start, keys, got["confirmed"])
        out["restored"] = getattr(newest(run, "restored"), "name", None)
        if failed is not None:
            code = failed
    if got["confirmed"]:
        say(f"the LUT stays in user place {LUT_PLACE} until the owner deletes it on the camera by hand ({WHERE}); the "
            "kit deletes nothing")
        say("to keep this finding in the coverage ledger (the looks file: the records' keys alone, no value), run these "
            "two once the lines above read right:")
        for line in record_commands(start, end.after, LUT_PLACE, bool(keys)):
            say(f"   {line}")
        say("and look at the camera's Import/Edit table again, so that the row for 16 is on record with its new reading "
            f"(the camera in Movie; nothing is chosen):\n   {look_command(run.root)}")
    return code


if __name__ == "__main__":
    sys.exit(main())
