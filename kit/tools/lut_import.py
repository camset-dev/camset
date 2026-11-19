"""Import one user LUT into the camera, and print which records of its settings file that changed: the evidence for the
camera's Manage User LUTs rows (Movie > Exposure/Color > Color/Tone), by Sony's documented ImportLUTFile, only as
docs/decisions/0026 allows: a .cube file from the clone's own private/lut/, into user place 16, on the owner's word for
the run, which the run carries as --allow "Manage User LUTs".

    .venv/bin/python -u kit/tools/lut_import.py private/lut/<pack>/<name>.cube --allow "Manage User LUTs" [--run kit2_lut]

One session, as every run of the kit has (docs/decisions/0015): the link, the camera's own picture of its screen (OSD)
as its eyes, no reader, and no key pressed nor anything answered on the camera's screen.
 1. Without --allow "Manage User LUTs", the owner's word, it stops before anything connects, as a prover does without
    its row's allowance; the allowance goes into the run's events.jsonl and lut_import.jsonl. The file is checked
    (camkit.link.lut_refused): a .cube file under the clone's own private/lut/ (where its path really ends, never
    through a link), a name Sony's reference takes, under 3,000,000 bytes, a .cube LUT's text. Refused, nothing sent.
 2. The start file is downloaded first, and the menu's lock after it waited out (camkit.session.wait_lock: LOCK_S, as
    there is no HDMI picture to watch). The camera saves its settings only on the shooting screen with a card in: a
    refused download is said, and the run ends there, nothing changed.
 3. BaseLookImportOperationEnableStatus is read and printed. Where it does not read Enable (1), or cannot be read,
    that is said with what the camera reads, and nothing is imported (Sony's reference allows the import only while it
    reads Enable; the camera may give it in Movie mode).
 4. The import (camkit.link.Link.import_lut: camlink's importlut, which checks the file again against the clone's
    folder it was built with, reads the camera's recording state and whether place 16 already holds a LUT, then gives
    ImportLUTFile a copy of the bytes it checked and waits for the camera's answer). Only the camera's
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
    definition, and a LUT's records may hold its name (docs/decisions/0016).
The LUT stays in user place 16 until the owner deletes it on the camera by hand (Manage User LUTs); the kit deletes
nothing.

Exit status (kit/exit_status.py): 0 when the camera took the LUT and the restore checked out, or a STOP came before the
import (nothing imported, said); 8 (EXIT_INCOMPLETE) when nothing was imported, or its answer did not come back at all,
and the camera is on its start file again; 7 (EXIT_REFUSED) when the kit's guards refused the import at the line; 5
(EXIT_RESTORE_BY_HAND) when the import was not confirmed, or the end found a screen no restore may go over, or the
camera was in Playback: put the start file back with kit/tools/upload_check.py, as RESTORE_BY_HAND names it; 4
(EXIT_UNRESTORED) when the start file could not be put back or a record did not go back; 1 when nothing was sent at
all (no allowance, the file refused, no link, the start download refused).
"""
import argparse
import os
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


def say(m: str) -> None:
    print(m, flush=True)


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
    ap.add_argument("--run", default="kit2_lut", help="the run folder, in the camera's runs/<model>_fw<fw>/")
    a = ap.parse_args()
    allowance = allowed(a.allow)
    lut = given_path(a.file)
    why = lut_refused(lut)
    if why:
        say(f"nothing was sent: {why}")
        return 1
    run = Run(a.run)
    run.log("lut_allowance", allow=list(a.allow), allowance=allowance)
    out = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "file": lut.resolve().name, "sha256": provenance.sha256(lut),
           "place": LUT_PLACE, "allowance": allowance}
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
    return code


if __name__ == "__main__":
    sys.exit(main())
