"""Prove Shoot Mode when the Shooting Mode Dial is set with the menu (Mode Dial Control Set; 2026-10-30).

    .venv/bin/python -u kit/provers/shootmode_run.py --start kit2_pass2/start_dialmenu_2026-10-30.DAT

The row opens a two-axis carousel: Up/Down chooses the family (stills, Movie, S&Q Motion, Time-lapse,
round), Left/Right the exposure mode within it (round); each family remembers its own mode, and the
orange title names the mode. Choosing a Movie or S&Q mode puts the whole camera in that mode (its
own menu), so every proof ends by uploading the start file again, and the next proof opens a new link.

First a look per family (Right until the title comes round), then one proof per family and mode:
the row, Right, Down to the family, Right to the mode, OK, a settings download, a diff with the start,
the start file back on. The memory-recall modes (MR, M1-M4) are left out: recalling a memory rewrites
dozens of settings. Proofs go to runs/<model>_fw<fw>/kit2_pass2/proofs.jsonl as "axis" proofs, one row per family
("Shoot Mode / Movie"), plus one "dialog" proof per family holding only the records every mode of the
family wrote alike (the family's own). Tagged with the context "Mode Dial Control Set = Set with Menu".
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import camset, ocr, paths  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.live import LiveCamera  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.session import verify_restore  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import Failed, option_key, to_shooting, vlm_option  # noqa: E402
from runner import (EXIT_UNRESTORED, add_scan_argument, changes_of, close_for_restore,  # noqa: E402
                    close_screen, end_session, load_scan, menu_from_shooting, proofs_file, restore_checked,
                    restoring, scan_position)

CONTEXT = "Mode Dial Control Set = Set with Menu"
FAMILIES = ["Stills", "Movie", "S&Q Motion", "Time-lapse"]       # Down order from stills, round
NAMES = ["Intelligent Auto", "Program Auto", "Aperture Priority", "Shutter Priority", "Manual Exposure"]
TITLE = (115, 50, 640, 112)


def lines(cam):
    return ocr.read([cam.frame.path])[cam.frame.path]


def mode_name(cam) -> str:
    """The mode the orange title names (an icon before it reads as letters: "A Manual Exposure")."""
    time.sleep(0.3)
    cam.refresh("reread")
    t = ocr.text_in(lines(cam), TITLE)
    k = option_key(t)
    for n in NAMES:
        if option_key(n) in k:
            return n
    m = re.search(r"MR.*", t)
    return ("MR " + re.sub(r"^MR\s*", "", m.group(0))).strip() if m else t.strip()


def open_row(cam, cycle, model):
    menu_from_shooting(cam)              # MENU, once more if it went unanswered after a download
    j = scan_position(cam, cycle)
    if j is None or go_to(cam, cycle, model, j, "Shoot Mode") is None:
        raise Failed("could not reach 'Shoot Mode' by the scan")
    cam.press("right")
    head = ocr.text_in(lines(cam), (0, 0, 640, 50))
    if cam.read().kind != "dialog" or "shoot mode" not in head.lower():
        raise Failed(f"Right on Shoot Mode opened {cam.read().kind} ({head!r})")


def look(cam, link, cycle, model, f: int) -> list:
    """The family's modes in Right order, from the one it remembers."""
    open_row(cam, cycle, model)
    for _ in range(f):
        cam.press("down")
    modes = [mode_name(cam)]
    for _ in range(20):
        cam.press("right")
        m = mode_name(cam)
        if m == modes[0]:
            break
        modes.append(m)
    close_screen(cam, link)
    return modes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", required=True, type=paths.run_arg,
                    help="the settings file with the dials set with the menu (kit2_pass2/... is in the camera's "
                         "runs/<model>_fw<fw>/)")
    add_scan_argument(ap)
    ap.add_argument("--families", default="0,1,2,3", help="which families to prove (0 stills ... 3 Time-lapse)")
    a = ap.parse_args()
    start = Path(a.start)
    cycle, model = load_scan(a.scan)
    run = Run("kit2_pass2")
    out = proofs_file(run, CONTEXT)
    hdmi = eyes_from_config(run)
    base = camset.read(start)
    try:
        with Link(run) as link:
            hdmi.attach(link)
            to_shooting(link, hdmi, "the start download")
            now = camset.read(link.download("before"))
            if camset.diff(base, now):
                sys.exit(f"the camera is not on {start.name} ({len(camset.diff(base, now))} records differ): load it first")
            time.sleep(5)
            cam = LiveCamera(link, hdmi, run)
            fams = [int(x) for x in a.families.split(",")]
            looked = None
            try:
                modes = {f: look(cam, link, cycle, model, f) for f in fams}
            except Exception as e:
                # a STOP, a refused press or the feed gone with the chooser open: closed with cleanup presses and
                # the start file put back before the link closes, since a dropped session applies the dialog on screen
                print(f"stopped: {type(e).__name__}: {e}", flush=True)
                looked = e
                close_for_restore(cam, link)
                ending = end_session(link, hdmi, start, "the restore after a stop", tag="stop")
        if looked is not None:
            restore_checked(run, ending, start)
            raise Failed(f"reading the Shoot Mode chooser: {looked}") from looked
        for f in fams:
            print(f"{FAMILIES[f]}: {modes[f]}", flush=True)
        for f in fams:
            todo = [m for m in range(len(modes[f])) if not modes[f][m].startswith("MR")]
            if f == 0:                                 # stills: its remembered mode is the start's; last
                todo = [m for m in todo if m != 0] + [0]
            recs = []
            for m in todo:
                time.sleep(4)
                with Link(run) as link:
                    hdmi.attach(link)
                    cam = LiveCamera(link, hdmi, run)
                    to_shooting(link, hdmi, "before the proof")
                    failed, ch = None, []
                    try:
                        open_row(cam, cycle, model)
                        for _ in range(f):
                            cam.press("down")
                        for _ in range(m):
                            cam.press("right")
                        got = mode_name(cam)
                        if got != modes[f][m]:
                            close_screen(cam, link)
                            raise Failed(f"{FAMILIES[f]}: the title reads {got!r}, not {modes[f][m]!r}")
                        chosen, seen_vlm = cam.frame.path.name, vlm_option(cam)
                        cam.press("enter")
                        notice = None
                        if cam.read().kind == "notice":
                            notice = {"text": ocr.text_in(lines(cam), (0, 0, 640, 480)), "frame": cam.frame.path.name}
                            print(f"   refused: {notice['text'][:90]!r}", flush=True)
                            cam.cancel_to_menu()
                        to_shooting(link, hdmi, "the download after OK")
                        time.sleep(1)
                        dat = link.download(f"shootmode-{f}-{m}")
                        ch = camset.diff(base, camset.read(dat))
                        rec = {"path": ["Shoot Mode"], "kind": "axis", "option": FAMILIES[f], "index": m,
                               "label": f"{FAMILIES[f]}: {modes[f][m]}", "shown": modes[f][m],
                               "final": f == 0 and m == 0, "chosen_frame": chosen, "vlm": seen_vlm,
                               "dat": dat.name, "base": start.name, "notice": notice, "applied": notice is None,
                               "changes": changes_of(ch)}
                        out.write(json.dumps(rec) + "\n")
                        out.flush()
                        recs.append(rec)
                        brief = ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in ch[:5]) or "no change"
                        print(f"   {FAMILIES[f]:10s} {modes[f][m]:18s} {brief}", flush=True)
                    except Exception as e:
                        # whatever the choice applied goes back before the run stops (decision 15): the error came
                        # after OK at the latest, before the upload that puts the start file back
                        print(f"stopped: {type(e).__name__}: {e}", flush=True)
                        failed = e
                        close_for_restore(cam, link)
                        ending = end_session(link, hdmi, start, "the restore after a stop", tag="stop")
                    if failed is None and ch:
                        with restoring("the restore after the proof"):      # refused or unanswered: exit 4
                            link.upload(start)
                if failed is not None:
                    restore_checked(run, ending, start)
                    raise Failed(f"{FAMILIES[f]}: {modes[f][m]}: {failed}") from failed
                if ch and verify_restore(run, start) != 0:
                    raise Failed(f"the start file did not take after {FAMILIES[f]}: {modes[f][m]}")
            # the family's own records: changed alike by every applied mode of the family
            applied = [r for r in recs if r["applied"]]
            if applied:
                common = None
                for r in applied:
                    kv = {(c["key"], json.dumps(c["after"])) for c in r["changes"]}
                    common = kv if common is None else common & kv
                own = [c for c in applied[0]["changes"] if (c["key"], json.dumps(c["after"])) in (common or set())]
                out.write(json.dumps({"path": ["Shoot Mode"], "kind": "dialog", "index": f, "label": FAMILIES[f],
                                      "shown": FAMILIES[f], "dat": applied[0]["dat"], "base": start.name,
                                      "applied": True, "family_of": [r["index"] for r in applied],
                                      "changes": own}) + "\n")
                out.flush()
                print(f"   {FAMILIES[f]}: its own records {[c['key'] for c in own]}", flush=True)
    except Failed as e:
        print(f"stopped: {e}", flush=True)
    finally:
        hdmi.close()
        out.close()
    n = verify_restore(run, start)
    print(f"at the end: {n} records differ from the start file", flush=True)
    if n != 0:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


if __name__ == "__main__":
    main()
