"""One picture on the card, so that the Playback rows have something to show: the shutter released once.

    .venv/bin/python -u kit/tools/take_picture.py            # the camera's owner at their own terminal

The one act of sound and motion the kit makes (docs/decisions/0002), and only as the camera's owner says at their own
terminal. Before anything connects it needs the owner's current blank-cards statement (camkit.statements; kit/tools/
owner_statement.py cards), the camera file's live_mode record (the playbook's section 16, step 6) and a person at a real
terminal, never a pipe or a shell an agent started. Then, on its own link (camkit.link.Link(picture=True): no press but
MENU, no dial, no property; camlink --picture), it downloads the start file and reads what one press of the shutter
would do (facts): the mode must be Stills (live_mode), and a definition's live setting of each name that reads so
refuses the picture: Drive Mode other than Single Shooting (a burst, a self-timer's lamp and beep, a bracket's lens
moves), Interval Rec Mode on, Pre-Capture on, Flash Mode other than Flash Off. A body's definition is recognised by
those setting names, as the kit's own proofs write them (a live setting: a whole record of section 0, no copy_for or
copy_of, every one of the name read); where it has none, the SDK's DriveMode, Interval_Rec_Mode and FlashMode are
asked, and what neither tells, or the SDK alone says (its values are stated, not proved), is put to the owner in the
question; the run's log keeps both readings. Silent Mode read as On says no shutter sound;
otherwise the question says one will be heard. The owner types "picture", which is kept dated in the reviewed scope
({"date", "picture": "once", "why"}: what they were told). Just before the release the screen must read as the shooting
screen, and a fresh download must say the same again. Nothing deletes the picture: it stays on the card. A release the
camera did not answer cleanly may have left the shutter held: nothing more is sent, RESTORE_BY_HAND is written, the
owner is told to switch the camera off, and the run exits EXIT_RESTORE_BY_HAND (5). Otherwise the run ends as every run
does, its start file put back where a record differs and checked (docs/decisions/0015); a refusal once connected exits
EXIT_REFUSED (7), a restore that does not check out EXIT_UNRESTORED (4), as does a link that never opened (a camlink
older than the kit, say), which says so and that nothing was sent. Another camera than the one the kit works on stops
it before anything is pressed.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, coverage, definitions, first_open, paths, safety, screen, session, statements  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link, LinkError  # noqa: E402
from camkit.runs import Run, mark_restore_by_hand  # noqa: E402
from runner import (EXIT_REFUSED, EXIT_RESTORE_BY_HAND, EXIT_UNRESTORED, cards_statement_refused,  # noqa: E402
                    read_json, restore_checked, statements_scope_or_exit)

STILLS = ("stills", "still")            # a live_mode mode's name the release goes in (compared as safety.plain)
# what one press must find, by the definition's setting names (the name, the label that lets the picture go), and the
# SDK's property and value standing in where a definition has none (CrDrive_Single, CrIntervalRecMode_OFF, CrFlash_Off)
NEEDS = {"drive": ("Drive Mode", "Single Shooting", "DriveMode", 1),
         "interval": ("Interval Rec Mode", "OFF", "Interval_Rec_Mode", 1),
         "precapture": ("Pre-Capture", "Off", None, None),
         "flash": ("Flash Mode", "Flash Off", "FlashMode", 2)}


class ShutterHeld(RuntimeError):
    """The release line went out and the camera did not answer it cleanly: the shutter may still be held."""


def live_mode_or_exit(camera: str) -> dict:
    """The camera file's live_mode ({"key", "modes"}), or the run stops before anything connects: it says which mode a
    file was saved in, and the release goes only in Stills."""
    f = definitions.camera_file(camera)
    lm = (read_json(f) if f.exists() else {}).get("live_mode") or {}
    if not lm.get("key") or not any(safety.plain(str(n)) in STILLS for n in (lm.get("modes") or {}).values()):
        sys.exit(f"take_picture.py: the camera file ({paths.shown(f)}) names no live_mode with a Stills mode, so the kit "
                 "cannot tell a stills mode from a movie one: find the record first (docs/REMAPPING_PLAYBOOK.md, section "
                 "16, step 6). Nothing was sent to the camera")
    return lm


def mode_of(live_mode: dict, dat: Path) -> str | None:
    """The shooting mode the settings file `dat` was saved in, by the camera file's live_mode (make_sample.file_mode)."""
    import make_sample
    return make_sample.file_mode({"camera": {"live_mode": live_mode}}, camset.read(dat))


def live_values(defn: dict, cs, name: str) -> list:
    """The value labels the definition's live settings called `name` hold in the settings file `cs` (a whole record of
    section 0, no copy_for or copy_of: never a memory slot's element or a stills or movie copy), None for one that
    cannot be told; [] where the definition has no such setting."""
    out = []
    for s in defn.get("settings") or []:
        key = str(s.get("key") or "")
        if safety.plain(str(s.get("name") or "")) != safety.plain(name) or not key.startswith("global:") \
                or "[" in key or "@" in key or s.get("copy_for") or s.get("copy_of"):
            continue
        rec = cs.get(0, int(coverage.record_base(key).split(":")[1], 16))
        v = coverage.value_of(s, rec.value()) if rec is not None else None
        out.append(next((lab for val, lab in s.get("values") or [] if val == v), None))
    return out


def sdk_value(link, prop):
    """The SDK property's current value (a read only), or None."""
    if not prop:
        return None
    try:
        got = link.get(prop).get("current")
    except Exception:       # noqa: BLE001 (a property the body does not list, a read that failed: not known)
        return None
    return got if isinstance(got, int) and not isinstance(got, bool) else None


def facts(link, defn: dict, cs) -> dict:
    """What one press of the shutter would do, for each of NEEDS: "ok", "no: <what it reads>" or "unknown" (the
    definition's live settings of its name in `cs`, every one of them, else the SDK's property); "silent", Silent Mode
    read as On; "stated", the NEEDS the SDK alone said were met, whose values the repository cannot show to be Sony's
    meaning rather than one body's (the question asks the owner of them too); and "read", what the definition and the
    SDK each gave, for the run's log: one run on a body whose definition has them says what the SDK's values mean."""
    out = {"stated": [], "read": {}}
    for what, (name, ok, prop, sdk_ok) in NEEDS.items():
        labels, got = live_values(defn, cs, name), sdk_value(link, prop)
        out["read"][what] = {"definition": labels, "sdk": got}
        if labels and None not in labels:
            bad = [x for x in labels if safety.plain(x) != safety.plain(ok)]
            out[what] = f"no: {name} reads {bad[0]}" if bad else "ok"
            continue
        out[what] = "unknown" if got is None else "ok" if got == sdk_ok else f"no: the SDK's {prop} reads {got}"
        if out[what] == "ok":
            out["stated"].append(what)
    out["silent"] = [safety.plain(x or "") for x in live_values(defn, cs, "Silent Mode")] == ["on"]
    return out


def refused(f: dict) -> str:
    """Why the facts refuse the picture, or ""."""
    no = [f[w][4:] for w in NEEDS if str(f.get(w, "")).startswith("no: ")]
    if no:
        return (f"{'; '.join(no)}: one picture needs Drive Mode on Single Shooting, interval shooting and Pre-Capture "
                "off and Flash Mode on Flash Off; set them by hand first (docs/decisions/0002)")
    return ""


def question(camera: str, mode: str, f: dict) -> str:
    sound = "Silent Mode reads On: the shutter makes no sound." if f["silent"] else "A shutter sound will be heard."
    unknown = [w for w in NEEDS if f.get(w) == "unknown" or w in f.get("stated", ())]
    told = {"drive": "Drive Mode is Single Shooting", "interval": "interval shooting is off",
            "precapture": "Pre-Capture is off (where the camera has it)", "flash": "no flash is attached or it is off"}
    only = (f"- The kit cannot tell everything from what it has proved: answer only if "
            f"{' and '.join(told[w] for w in unknown)}.\n" if unknown else "")
    return (f"The camera {camera} takes one picture, so the Playback rows have something to show: the kit releases the "
            f"shutter once, in {mode} on the shooting screen. The picture stays on the card; the kit never deletes it.\n"
            "- The camera focuses first: the lens may move, and the AF illuminator may light where it is on.\n"
            f"- {sound}\n{only}".rstrip())


def shooting_now(link, eyes) -> bool:
    """Whether the screen reads as the shooting screen now (a black frame read on the camera's own picture), never the
    camera's playback view (camkit.session.kind_seen: read so while the camera says it is in Playback)."""
    return session.kind_seen(link, eyes.grab(save=False)) == "shooting"


def main(argv=None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="kit2_picture", help="run folder in the camera's runs/<model>_fw<fw>/")
    a = ap.parse_args(argv)
    camera = (paths.camera() or (None,))[0]
    if camera is None:
        sys.exit(paths.no_camera_message())
    scope, scope_file = statements_scope_or_exit("take_picture.py")
    why = cards_statement_refused("take_picture.py")
    if why:
        sys.exit(f"take_picture.py: {why}. Nothing was sent to the camera")
    live = live_mode_or_exit(camera)
    marker = statements.agent_shell()
    if marker or not sys.stdin.isatty():
        sys.exit("take_picture.py: only the camera's owner answers its question, in a terminal of their own "
                 f"({f'{marker} says an agent started this shell' if marker else 'standard input is no terminal'}). "
                 "Nothing was sent to the camera")
    dpath = definitions.path(camera)
    defn = read_json(dpath) if dpath.exists() else {}
    run = Run(a.run)
    eyes = eyes_from_config(run)
    stopped, ending, before, held = "", None, None, ""
    try:
        with Link(run, picture=True) as link:
            other = first_open.other_body(link, run.root.name)
            if other:
                sys.exit(f"take_picture.py: {other}: nothing was sent to the camera")
            eyes.attach(link)
            if screen.read(eyes.grab(save=False)).kind in ("menu", "tiles"):
                link.press("menu", cleanup=True)
                time.sleep(1.0)
            session.wait_for(eyes, ("shooting",), "the start file's download", link=link)
            before = link.download("before")
            try:
                stopped = picture(link, eyes, camera, live, defn, scope, scope_file, before)
            except ShutterHeld as e:
                held = str(e)
            except (Exception, SystemExit) as e:    # before the release: the end below runs all the same
                stopped = f"{type(e).__name__}: {e}"
            if held:
                # nothing more is sent: a press, a download or an upload with the shutter held could take more pictures
                print(f"take_picture.py: the release was not answered cleanly ({held}): the shutter may be held. "
                      "Switch the camera off now. Once it is on again and reachable, put the start file back with\n"
                      f"  .venv/bin/python -u kit/tools/upload_check.py {run.dir.name}/dat/{before.name}", flush=True)
                try:
                    mark_restore_by_hand(run.root, run.dir.name, before, f"the shutter may be held ({held})")
                except OSError as e:
                    print(f"RESTORE_BY_HAND could not be written ({e}): start no run before that upload", flush=True)
                sys.exit(EXIT_RESTORE_BY_HAND)
            if stopped:
                print(f"take_picture.py: {stopped}: no picture was taken", flush=True)
            session.wait_for(eyes, ("shooting",), "the settings download after the picture", link=link)
            ending = session.finish(link, before)
        restored = restore_checked(run, ending, before)
    except Exception as e:
        if isinstance(e, LinkError) and not e.opened:       # before the link's ready line: nothing was sent
            print(f"take_picture.py: {e}\nthe link never opened: nothing was sent to the camera", flush=True)
        else:
            print(f"take_picture.py: {type(e).__name__}: {e}; the start file is not known to be back"
                  + (f": put it back with kit/tools/upload_check.py {run.dir.name}/dat/{before.name}" if before else ""),
                  flush=True)
        restored = False
    finally:
        eyes.close()
    if not restored:
        sys.exit(EXIT_UNRESTORED)
    if stopped:
        sys.exit(EXIT_REFUSED)


def picture(link, eyes, camera: str, live: dict, defn: dict, scope: dict, scope_file: Path, before: Path) -> str:
    """The release, once, or why it was not made: Stills and the facts by the start file `before`, the owner's answer at
    the terminal (kept as the dated picture statement), then just before it the shooting screen and a fresh download
    saying the same. ShutterHeld once the release line went out and was not answered cleanly."""
    mode = mode_of(live, before)
    f = facts(link, defn, camset.read(before))
    log = getattr(getattr(link, "run", None), "log", None)
    if callable(log):
        log("picture_facts", download=Path(before).name, read=f["read"], stated=f["stated"])
    if safety.plain(mode or "") not in STILLS:
        return f"the camera is in {mode or 'a mode its live_mode does not name'}, not Stills"
    if refused(f):
        return refused(f)
    why = statements.ask(question(camera, mode, f), "picture")
    if why:
        return why
    if scope_file.is_file():
        scope = statements_scope_or_exit("take_picture.py")[0]      # as it is now, the person having answered
    statements.add(scope_file, scope, {
        "date": statements.today(), "picture": "once",
        "why": f"the owner typed it at the terminal (kit/tools/take_picture.py), told: {mode}; "
               f"{'no shutter sound' if f['silent'] else 'a shutter sound'}; "
               + "; ".join(f"{w} {f[w]}" for w in NEEDS)})
    time.sleep(5)                       # the menu lock after a download (proving.base.LOCK_S) has passed
    if not shooting_now(link, eyes):
        return "the screen no longer reads as the shooting screen"
    again = link.download("before-release")
    if safety.plain(mode_of(live, again) or "") not in STILLS:
        return "the camera has left Stills since the question"
    now = facts(link, defn, camset.read(again))
    if callable(log):
        log("picture_facts", download=Path(again).name, read=now["read"], stated=now["stated"])
    if refused(now) or any(now[w] != f[w] for w in NEEDS):
        return f"what one press would do has changed since the question ({refused(now) or 'a reading changed'})"
    time.sleep(5)
    if not shooting_now(link, eyes):
        return "the screen no longer reads as the shooting screen"
    try:
        link.release(screen="shooting")
    except LinkError as e:
        raise ShutterHeld(f"{type(e).__name__}: {e}") from e
    print("the shutter was released once; the picture stays on the card", flush=True)
    time.sleep(3)
    return ""


if __name__ == "__main__":
    main()
