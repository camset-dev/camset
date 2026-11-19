"""Import one user LUT into the camera, and print which records of its settings file that changed: the evidence for the
camera's Manage User LUTs rows (Movie > Exposure/Color > Color/Tone), by Sony's documented ImportLUTFile, as the owner
allowed it on 2026-11-19 for .cube files under their own private/lut/.

    .venv/bin/python -u kit/tools/lut_import.py private/lut/<pack>/<name>.cube
    .venv/bin/python -u kit/tools/lut_import.py FILE.cube [--run kit2_lut]

One session, as every run of the kit has (docs/decisions/0015): the link alone, as kit/tools/upload_check.py opens it,
no eyes and no reader, and no key pressed nor anything answered on the camera's screen.
 1. The file is checked before anything connects (camkit.link.lut_refused): a .cube file under the clone's own
    private/lut/ (where its path really ends, never through a link), a name Sony's reference takes, under 3,000,000
    bytes, a .cube LUT's text. It goes into user place 16, the one place docs/decisions/0026 allows. Refused, nothing
    sent.
 2. The start file is downloaded first. The camera saves its settings only on the shooting screen with a card in: a
    refused download is said, and the run ends there, nothing changed.
 3. BaseLookImportOperationEnableStatus is read and printed. Where it does not read Enable (1), or cannot be read,
    that is said with what the camera reads, and nothing is imported (Sony's reference allows the import only while it
    reads Enable; the camera may give it in Movie mode).
 4. The import (camkit.link.Link.import_lut: camlink's importlut, which checks the file again, reads the camera's
    recording state and whether the place already holds a LUT, then calls ImportLUTFile and waits for the camera's
    answer). Only the camera's ImportLUTFile_Result_OK is an import; a refusal, no answer or a dropped session is said
    as that, never as a success.
 5. A download, and every record that differs from the start file, by key, with the setting the camera's definition
    names on it and its values: the mapping's evidence of what the file holds of a user LUT. Values a camera holds stay
    in the run (docs/decisions/0016): never copy them into a public file.
 6. The end every run has: the start file uploaded when anything differs, the camera's restart waited for, a download
    compared with the start file (camkit.session.verify_restore), the records the import changed left out of that
    count and said by key. Those that did not go back are the LUT's own state, which no settings file puts back:
    expected, said, not an error. The LUT stays in its user place until the owner deletes it on the camera by hand
    (Manage User LUTs); the kit deletes nothing.
 7. Once the camera took the LUT, the two kit/tools/coverage.py --record commands that keep the finding in the
    coverage ledger, for Manage User LUTs and its Import/Edit (Movie, Exposure/Color > Color/Tone), with this run's
    start download and the one after the import: run them as printed, once the output reads right. They write one look
    each into the looks file (private/evidence/<model>_fw<fw>/, the mapper's own), the records that changed by key
    alone, never a value: --did act when records changed, which the ledger counts as a hand check that changed a record
    ("proved by hand"; its public form says only that the row changed a record), --did choose when none did ("tested,
    no record changes", private). The looks file's "by" says "hand", the one its vocabulary has for a change made
    outside the kit's walks; the note says it was this tool. No proof line is written: a proof's values would reach the
    definition, and a LUT's records may hold its name (docs/decisions/0016).

The run's events.jsonl keeps every command and answer (the LUT's name, size and SHA-256, never its content), and its
lut_import.jsonl one line per run: the file's name and SHA-256, the place, the enable status, the camera's answer, the
downloads' names and the records' keys (no value).

Exit status (kit/exit_status.py): 0 when the camera took the LUT and the restore checked out, or a STOP came before the
import (nothing imported, said); 8 (EXIT_INCOMPLETE) when nothing was imported, or the import is not confirmed, and the
camera is on its start file again; 7 (EXIT_REFUSED) when the kit's guards refused the import at the line; 4
(EXIT_UNRESTORED) when the start file could not be put back or its restore did not check out; 1 when nothing was sent
at all (the file or the place refused, no link, the start download refused).
"""
import argparse
import os
import shlex
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, definitions, jsonl, paths, provenance, safety  # noqa: E402
from camkit.link import LUT_OK, LUT_PLACE, Link, LinkError, LutNotImported, StopRequested, lut_refused  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.session import Ending, compared, put_back, verify_restore  # noqa: E402
from exit_status import EXIT_INCOMPLETE, EXIT_REFUSED, EXIT_UNRESTORED  # noqa: E402

ENABLE_PROPERTY = "BaseLookImportOperationEnableStatus"
ENABLE = 1                       # CrBaseLookImportOperation_Enable (kit/common/lut_file.h kEnable)
STATUS_WORDS = {0: "Disable", 1: "Enable"}
TRIES, PAUSE = 4, 10.0           # the download after the import, as a session's last one is tried (camkit.session.ended)
ELEMENTS_SAID = 32               # the most elements of one array record said
WHERE = "Movie > Exposure/Color > Color/Tone > Manage User LUTs"


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


def download_after(link, tag: str, say=print):
    """The camera's download after the import, tried TRIES times PAUSE s apart (the camera may refuse one while it
    shows a notice); None when it kept refusing."""
    for attempt in range(TRIES):
        try:
            return link.download(tag)
        except LinkError as e:
            if attempt == TRIES - 1:
                break
            say(f"the settings download was refused ({e}); trying again in {PAUSE:g} s")
            time.sleep(PAUSE)
    return None


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
NOTE = ("a user LUT imported through Sony's ImportLUTFile by kit/tools/lut_import.py, not by hand, as the owner allowed "
        "it on 2026-11-19")


def record_commands(start: Path, after: Path, place: int, changed: bool) -> list:
    """The kit/tools/coverage.py --record commands that keep this run's finding in the coverage ledger (the module
    docstring's step 7): one for Import/Edit, with the place as its option (User<place>, as the camera's table names
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("file", help="the .cube file, under the clone's own private/lut/")
    ap.add_argument("--run", default="kit2_lut", help="the run folder, in the camera's runs/<model>_fw<fw>/")
    a = ap.parse_args()
    lut = given_path(a.file)
    why = lut_refused(lut)
    if why:
        print(f"nothing was sent: {why}", flush=True)
        return 1
    run = Run(a.run)
    record = {"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "file": lut.resolve().name, "sha256": provenance.sha256(lut),
              "place": LUT_PLACE}
    status, called, result, start, after, changes, ending = None, False, None, None, None, [], None
    code = 0
    try:
        with Link(run) as link:
            try:
                start = link.download("start")
            except LinkError as e:
                print(f"the camera refused the start download ({e}): it saves its settings only on the shooting "
                      "screen, with a card in. Close any menu on the camera by hand and run this again; nothing was "
                      "imported", flush=True)
                return 1
            print(f"start file: {start.name}", flush=True)
            status, words = enable_status(link)
            print(f"{ENABLE_PROPERTY} {words}", flush=True)
            if status != ENABLE:
                print(f"the camera does not allow a LUT import now: {ENABLE_PROPERTY} {words}, and Sony's reference "
                      f"allows the import only while it reads Enable ({ENABLE}); nothing was imported. The camera may "
                      "give it in Movie mode: switch to Movie, then run this again", flush=True)
                code = EXIT_INCOMPLETE
            else:
                try:
                    r = link.import_lut(lut)
                    called, result = True, r.get("result")
                    print(f"{LUT_OK}: {record['file']} is in user place {LUT_PLACE} (the camera answered in "
                          f"{r.get('ms')} ms)", flush=True)
                except LutNotImported as e:
                    called, result = e.called, e.reply.get("result") or e.reply.get("cause")
                    print(f"no import confirmed: {e}", flush=True)
                    if called:
                        print("the SDK was asked, so the camera may have changed: its settings are downloaded and "
                              "compared all the same, and the start file put back", flush=True)
                    code = EXIT_INCOMPLETE
                except safety.Refused as e:
                    print(f"the kit's guards refused the import ({e}); nothing was imported", flush=True)
                    code = EXIT_REFUSED
                except StopRequested as e:
                    print(f"a STOP was asked for before the import ({e}); nothing was imported", flush=True)
                except LinkError as e:
                    # no answer at all (camlink gone, the link in a network error): whether the SDK was asked is not
                    # known, so the camera is taken as changed
                    called, result = True, None
                    print(f"the import's answer did not come ({e}): whether the LUT went in is not known; the "
                          "camera's settings are downloaded and compared all the same", flush=True)
                    code = EXIT_INCOMPLETE
            after = download_after(link, "after-lut" if called else "after")
            if after is None:
                print(f"the camera kept refusing the settings download: the start file is not restored; put it back "
                      f"with kit/tools/upload_check.py {start}", flush=True)
                code = EXIT_UNRESTORED
            else:
                changes = compared(start, after, say=lambda m: print(m, flush=True))
                print(f"{len(changes)} records differ from the start file {start.name} in {after.name}"
                      + (", as the import left them:" if called and changes else ""), flush=True)
                names = setting_names()
                for c in changes:
                    print(change_line(c, names), flush=True)
                ending = put_back(link, Ending(after, changes), start, say=lambda m: print(m, flush=True))
    except LinkError as e:
        if start is None:
            print(f"no link to the camera ({e}); nothing was sent", flush=True)
            return 1
        print(f"the session ended early ({e}): the start file may not be on the camera; put it back with "
              f"kit/tools/upload_check.py {start}", flush=True)
        code = EXIT_UNRESTORED
    keys = [c.key for c in changes]
    not_back = []
    if ending is not None and ending.uploaded:
        n = verify_restore(run, start, expected=frozenset(keys), say=lambda m: print(m, flush=True))
        restored = newest(run, "restored")
        if n is None:
            print("the restore could not be checked: the camera did not answer after its restart. Check that it is on "
                  f"and connected, then run kit/tools/upload_check.py {start}", flush=True)
            code = EXIT_UNRESTORED
        elif n:
            print(f"the restore did not check out: {n} records the import did not change still differ from the start "
                  f"file. Look at those settings on the camera, then run kit/tools/upload_check.py {start}", flush=True)
            code = EXIT_UNRESTORED
        if restored is not None and n is not None:
            left = {c.key for c in compared(start, restored, say=lambda m: None)}
            not_back = [k for k in keys if k in left]
            record["restored"] = restored.name
        if not_back:
            print(f"the restore put back {len(keys) - len(not_back)} of the {len(keys)} records the import changed; "
                  f"{len(not_back)} did not go back: {', '.join(not_back)}. A user LUT is state no settings file puts "
                  "back: this is expected, not an error", flush=True)
        elif n == 0:
            print(f"the restore put back all {len(keys)} records the import changed", flush=True)
    if called and result == LUT_OK:
        print(f"the LUT stays in user place {LUT_PLACE} until the owner deletes it on the camera by hand ({WHERE}); the "
              "kit deletes nothing", flush=True)
        if after is not None:
            print("to keep this finding in the coverage ledger (the looks file: the records' keys alone, no value), run "
                  "these two once the lines above read right:", flush=True)
            for line in record_commands(start, after, LUT_PLACE, bool(keys)):
                print(f"   {line}", flush=True)
    record.update(enable_status=status, called=called, result=result, start=start.name if start else None,
                  after=after.name if after else None, records_changed=keys, not_back=not_back, exit=code)
    jsonl.append(run.dir / "lut_import.jsonl", record)
    return code


if __name__ == "__main__":
    sys.exit(main())
