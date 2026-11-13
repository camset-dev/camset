"""Pass 3: rows greyed by another setting. Switch the blocker, walk and prove what it opened, put
everything back.

    .venv/bin/python -u kit/pass3_run.py [--only "Shutter Type"]

Per blocker (BLOCKERS: the camera's own reason for each greyed row, kit2_pass1/greyed.json); every run folder here
is in the camera's runs/<model>_fw<fw>/ (camkit.paths), and so are the BLOCKERS' "scan", "map" and "run":
  1. download the settings (the run's start), choose the blocker's unblocking option (the same
     moves as a proof: its row, Right, the option by its label, OK; first each of its "first" states,
     the same way), download again;
  2. walk the opened row as pass 1 does (kit/crawl_run.py, into kit2_pass3);
  3. read its labels and build that run's map (kit/pass1_labels.py; kit/tiebreak.py, the third reader
     where the first two differ; kit/pass1_map.py --own, that run's map only, not pass 1's map_all.json);
  4. prove its rows (kit/prove_run.py --map kit2_pass3/map.json): their base is the switched
     state, and a failed row restores that state;
  5. upload the start file and check nothing differs from it.
Stops at the first blocker whose restore does not check out.

Blockers switched by a file ("set": record values written into the start file and uploaded) are retired and
refused: that is a file edited by a script, which docs/decisions/0006 forbids since a hand-edited file
boot-looped the a1 II on 2026-11-01, and Link.upload refuses it (its bytes are no download's). For such a
state, change the setting on the camera (the menu, or the owner by hand), watch it take, download it, and
prove from that download with prove_run.py --start.
"""
import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ROOT, camset, models, paths, session  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link, LinkError, StopRequested  # noqa: E402
from camkit.live import LiveCamera  # noqa: E402
from camkit.vlm import check_readers  # noqa: E402
from camkit.runs import Run  # noqa: E402
from camkit.screen import same_position  # noqa: E402
from crawl_run import go_to  # noqa: E402
from prove_run import (PASS1, Failed, enter_any, main_name, move_to, option_index, option_key,  # noqa: E402
                       to_shooting)
from runner import EXIT_UNRESTORED, add_scan_argument, end_session, load_scan, read_json, restoring  # noqa: E402

PY = sys.executable                  # the kit's own Python on every OS (.venv/bin or .venv\Scripts)
RUN_ROOT = paths.module_root()       # the camera's runs, runs/<model>_fw<fw>/
P3 = RUN_ROOT / "kit2_pass3"
# row of the blocker, the option that lifts it, the top-level row to walk afterwards. This table is the ILCE-1M2's
# (firmware 4.00, from its pass 1's greyed.json and the camera's own reasons): another body needs its own, and
# main() refuses to run it on one. TODO: into data/<model>_fw<fw>/ (docs/decisions/0019, 0020)
BLOCKERS = [
    {"row": ["Shutter Type"], "to": "Mechanical Shutter", "walk": "Long Exposure NR"},
    {"row": ["Drive Mode"], "to": "Continuous Shooting", "walk": "Pre-Capture Settings"},
    {"row": ["Anti-flicker Set.", "Var. Shutter"], "to": "On", "walk": "Anti-flicker Set."},
    {"row": ["SteadyShot Adjust."], "to": "Manual", "walk": "Focal Length"},
    {"row": ["Gamma Display Assist"], "to": "Off", "walk": "Display LUT"},
    # not a greyed row: a setting that splits others by orientation (user, 2026-10-29). With it on,
    # Focus Area proved with the camera level should change only the horizontal records.
    {"row": ["Switch V/H AF Area"], "to": "AF Point + AF Area", "prove": ["Focus Area"],
     "context": "Switch V/H AF Area = AF Point + AF Area, camera level", "on_request": True},
    # switched by a file (2026-10-30): "set" records go into the start file, which is uploaded and
    # checked; "walk" may name several top-level rows
    # Zoom opens the zoom itself (nothing to prove) and Zoom Range was proved before (2026-10-30);
    # HLG Still Image also wants JPEG/HEIF Switch on HEIF (its notice once File Format was HEIF)
    {"row": ["File Format"], "to": "HEIF (both slots, JPEG/HEIF Switch HEIF 4:2:0)",
     "set": {0x01d8: 1, 0x01e6: 2, 0x01f2: 2}, "walk": ["HLG Still Image"]},
    # Shoot Mode A with the mode dial set from the menu: what the menu's Shoot Mode writes (0x10b6,
    # 0x13e0; shootmode_run.py), with Mode Dial Control Set's menu value
    {"row": ["Shoot Mode"], "to": "Aperture Priority (dial set with the menu)",
     "set": {0x13ad: 1, 0x10b6: 2, 0x13e0: 3}, "walk": ["ISO AUTO Min. SS", "Interval Shoot Func."]},
    # HDMI-side blockers: run with the OSD eyes (CAMSET_EYES=osd), since the HDMI feed changes
    {"row": ["HDMI Info. Display"], "to": "Off", "set": {0x049c: 1},
     "walk": ["Aspect Marker Level", "Touch Panel Settings"]},
    {"row": ["HDMI Output Settings", "Rec. Media dur HDMI Output"], "to": "Off (HDMI only)", "set": {0x0492: 1},
     "walk": ["HDMI Output Settings"]},
    # Movie mode (load start_reg_movie_2026-10-30.DAT first): each movie file format has its own
    # Record Setting and Rec Frame Rate records; XAVC S 4K's were proved in the Movie batch. Rec Frame
    # Rate is OSD-only in the scope (it changes the HDMI signal) and the OSD needs a Movie scan of its
    # own; the S-I formats grey Record Setting out; XAVC HS 8K (0x0200 = 5) does not load from a file
    *[{"row": ["Movie File Format", name], "to": name, "set": {0x0200: code, 0x16ae: 1 if "HD" in name else 8},
       "walk": ["Movie Settings"], "scan": "kit2_page_scan_movie_dm", "run": f"kit2_pass3_mv{code}",
       "context": f"Movie mode, File Format {name}", "rows": ["Movie Settings > Record Setting"]}
      for code, name in ((6, "XAVC HS 4K"), (8, "XAVC S HD"))],
    # over the OSD (run with CAMSET_EYES=osd; the scans are OSD scans: page keys differ between eyes).
    # "OSD stills" wants the stills start loaded, "OSD movie" Movie mode (start_reg_movie_2026-10-30.DAT)
    {"row": ["OSD stills", "HDMI Info. Display"], "to": "Off", "set": {0x049c: 1},
     "walk": ["Aspect Marker Level", "Touch Panel Settings"], "scan": "kit2_page_scan_osd",
     "run": "kit2_pass3_osd", "prove_eyes": "osd-all"},
    *[{"row": ["OSD movie", f"Movie File Format {name}"], "to": name,
       "set": {0x0200: code, 0x16ae: 1 if "HD" in name else 8}, "walk": ["Movie Settings"],
       "scan": "kit2_page_scan_movie_dm_osd", "run": f"kit2_pass3_osd_mv{code}",
       "context": f"Movie mode, File Format {name}", "rows": ["Movie Settings > Rec Frame Rate"],
       "prove_eyes": "osd-all"}
      for code, name in ((6, "XAVC HS 4K"), (8, "XAVC S HD"), (9, "XAVC S-I 4K"), (10, "XAVC S-I HD"))],
    # S&Q's Record Setting per movie file format (2026-10-31): 0x0256 was proved with XAVC S 4K, and
    # 0x0254 (unproved) shares XAVC S 4K's codes; Movie mode loaded first, as above
    *[{"row": ["S&Q formats", f"Movie File Format {name}"], "to": name,
       "set": {0x0200: code, 0x16ae: 1 if "HD" in name else 8}, "walk": ["S&Q Settings"],
       "scan": "kit2_page_scan_movie_dm", "run": f"kit2_pass3_sq{code}",
       "context": f"Movie mode, File Format {name}", "rows": ["S&Q Settings > Record Setting"]}
      for code, name in ((6, "XAVC HS 4K"), (8, "XAVC S HD"))],
    # S&Q keeps a Record Setting record per File Format and S&Q Rec Frame Rate (XAVC S 4K: 60p 0x0256,
    # 24p 0x0258; 2026-10-31): the rest of the grid, each switched by a file
    *[{"name": f"S&Q grid {fname} {rname}", "row": ["S&Q grid", f"{fname} at {rname}"], "to": rname,
       "set": {0x0200: code, 0x16ae: 1 if "HD" in fname else 8, 0x0240: rc}, "walk": ["S&Q Settings"],
       "scan": "kit2_page_scan_movie_dm", "run": f"kit2_pass3_sq{code}_{rc}",
       "context": f"Movie mode, File Format {fname}, S&Q Rec Frame Rate {rname}",
       "rows": ["S&Q Settings > Record Setting"], "on_request": True}
      for code, fname in ((6, "XAVC HS 4K"), (7, "XAVC S 4K"), (8, "XAVC S HD"))
      for rc, rname in ((0, "60p"), (2, "30p"), (4, "24p"), (5, "120p"))
      if (code, rc) != (7, 4)],
    # Movie mode's Record Setting the same way: per File Format and its Rec Frame Rate (XAVC S 4K at
    # 30p offers 60M, which 0x0218, its 60p record, does not; 2026-10-31). 0x190c, the rate in use,
    # is set with it (60p 1, 30p 3, 24p 5, 120p 7)
    # A file that changes only the frame rate is refused (its Record Setting may not exist at the new
    # rate), so the chain loads the File Format by a file and the rate is chosen in the menu, where
    # the camera picks a Record Setting that fits
    # 24p puts HDMI out at 24p, which the capture dongle cannot take: those run over the OSD
    # (CAMSET_EYES=osd, the OSD movie scan), as 8K does
    *[{"name": f"Movie grid {fname} {rname}", "row": ["Movie Settings", "Rec Frame Rate"], "to": rname,
       "map": "kit2_crawl_movie/map.json", "expect": {0x0200: code},
       "labels": ["60p", "24p", "120p"] if fname == "XAVC HS 4K" else ["60p", "30p", "24p", "120p"],
       "walk": ["Movie Settings"], "run": f"kit2_pass3_mv{code}_{rr}",
       "scan": "kit2_page_scan_movie_dm_osd" if rname == "24p" else "kit2_page_scan_movie_dm",
       **({"prove_eyes": "osd-all"} if rname == "24p" else {}),
       "context": f"Movie mode, File Format {fname}, Rec Frame Rate {rname}",
       "rows": ["Movie Settings > Record Setting"], "on_request": True}
      for code, fname in ((6, "XAVC HS 4K"), (7, "XAVC S 4K"), (8, "XAVC S HD"), (9, "XAVC S-I 4K"), (10, "XAVC S-I HD"))
      for rr, rname in ((0, "60p"), (2, "30p"), (4, "24p"), (5, "120p"))
      if (fname, rname) != ("XAVC HS 4K", "30p")],
    # XAVC HS 8K at 24p (0x0210?): 8K chosen in the menu first by the chain, all over the OSD
    {"name": "Movie grid XAVC HS 8K 24p", "row": ["Movie Settings", "Rec Frame Rate"], "to": "24p",
     "map": "kit2_crawl_movie/map.json", "expect": {0x0200: 5}, "labels": ["30p", "24p"],
     "walk": ["Movie Settings"], "run": "kit2_pass3_mv5_4", "scan": "kit2_page_scan_movie_dm_osd",
     "prove_eyes": "osd-all", "context": "Movie mode, File Format XAVC HS 8K, Rec Frame Rate 24p",
     "rows": ["Movie Settings > Record Setting"], "on_request": True},
    # XAVC HS 8K does not load from a file, so Movie mode's File Format is chosen from the menu (its
    # row and options from the Movie crawl's map; run with --scan for that Movie scan, CAMSET_EYES=osd)
    {"name": "Movie 8K", "row": ["File Format"], "to": "XAVC HS 8K", "map": "kit2_crawl_movie/map.json",
     "walk": ["Movie Settings"], "scan": "kit2_page_scan_movie_dm_osd", "run": "kit2_pass3_osd_mv5",
     "context": "Movie mode, File Format XAVC HS 8K", "prove_eyes": "osd-all",
     "rows": ["Movie Settings > Record Setting", "Movie Settings > Rec Frame Rate"]},
    # PAL (2026-11-06): the owner set NTSC/PAL Selector to PAL by hand (docs/decisions/0008) and moved the switch to
    # Movie. Under PAL every frame-rate list holds the PAL rates (50p, 25p, 100p), which the NTSC proofs never
    # chose, so their values had no names. Each File Format is chosen in the menu, Movie Settings walked again in
    # that state (its lists differ from the NTSC map's) and its Rec Frame Rate proved; then S&Q's and Time-lapse's
    # frame rates. All over the OSD (CAMSET_EYES=osd, the OSD Movie scan): a change of rate changes the HDMI signal
    *[{"name": f"PAL {fname}", "row": ["File Format"], "to": fname, "map": "kit2_crawl_movie/map.json",
       "walk": ["Movie Settings"], "scan": "kit2_page_scan_movie_osd", "run": f"kit2_pal_mv{code}",
       "context": f"Movie mode, PAL, File Format {fname}", "prove_eyes": "osd-all",
       "rows": ["Movie Settings > Rec Frame Rate"], "on_request": True}
      for code, fname in ((7, "XAVC S 4K"), (6, "XAVC HS 4K"), (8, "XAVC S HD"), (9, "XAVC S-I 4K"), (10, "XAVC S-I HD"),
                          (5, "XAVC HS 8K"))],
    {"name": "PAL S&Q", "row": ["File Format"], "to": "XAVC S 4K", "map": "kit2_crawl_movie/map.json",
     "walk": ["S&Q Settings"], "scan": "kit2_page_scan_movie_osd", "run": "kit2_pal_sq",
     "context": "Movie mode, PAL", "prove_eyes": "osd-all", "on_request": True,
     "rows": ["S&Q Settings > Frame Rate Settings > Rec Frame Rate", "S&Q Settings > Frame Rate Settings > Frame Rate"]},
    {"name": "PAL Time-lapse", "row": ["File Format"], "to": "XAVC S 4K", "map": "kit2_crawl_movie/map.json",
     "walk": ["Time-lapse Settings"], "scan": "kit2_page_scan_movie_osd", "run": "kit2_pal_tl",
     "context": "Movie mode, PAL", "prove_eyes": "osd-all", "on_request": True,
     "rows": ["Time-lapse Settings > Frame Rate Settings > Rec Frame Rate"]},
    # ... and each format again from another saved rate: a row's last proof is the option it opened on, which changes
    # nothing, so the rate each list opened on after the switch to PAL (the camera's own, decision 16) is proved only
    # from another start. "first" is chosen in the menu before the blocker's own switch; the restore puts both back
    *[{"name": f"PAL {fname} from {rate}",
       "first": [{"row": ["File Format"], "to": fname, "map": "kit2_crawl_movie/map.json"}],
       "row": ["Movie Settings", "Rec Frame Rate"], "to": rate, "map": f"kit2_pal_mv{code}/map.json",
       "walk": ["Movie Settings"], "scan": "kit2_page_scan_movie_osd", "run": f"kit2_pal_mv{code}_b",
       "context": f"Movie mode, PAL, File Format {fname}, Rec Frame Rate {rate}", "prove_eyes": "osd-all",
       "rows": ["Movie Settings > Rec Frame Rate"], "on_request": True}
      for code, fname, rate in ((7, "XAVC S 4K", "25p"), (6, "XAVC HS 4K", "100p"), (8, "XAVC S HD", "25p"),
                                (9, "XAVC S-I 4K", "25p"), (10, "XAVC S-I HD", "25p"))],
    # Log Shooting On opens the rows it greys (Select LUT, Display LUT, the rest of Log Shooting
    # Setting; 2026-10-31)
    {"name": "Movie Log", "row": ["Log Shooting Setting", "Log Shooting"], "to": "On (Flexible ISO)",
     "map": "kit2_crawl_movie/map.json", "set": {0x101f: 1},
     "walk": ["Log Shooting Setting", "Select LUT", "Display LUT"], "scan": "kit2_page_scan_movie_dm",
     "run": "kit2_pass3_log", "context": "Movie mode, Log Shooting On"},
    # Auto/Manual Swt. Set.'s rows answer "not available: Exposure Ctrl Type P/A/S/M Mode" (2026-10-31)
    {"name": "Movie Flexible", "row": ["Exposure Ctrl Type"], "to": "Flexible Exp. Mode",
     "map": "kit2_crawl_movie/map.json", "set": {0x02b0: 1},
     "walk": ["Auto/Manual Swt. Set."], "scan": "kit2_page_scan_movie_dm",
     "run": "kit2_pass3_flex", "context": "Movie mode, Exposure Ctrl Type Flexible Exp. Mode"},
    # the finder rows stay greyed with VF(Manual) while HDMI shows the info display (frame 25181): with
    # HDMI Info. Display Off the camera's own screen is in use, VF(Manual) puts it in the finder, and
    # the SDK's OSD grab is the eyes (run with CAMSET_EYES=osd; user's idea, 2026-10-31)
    {"name": "Finder", "row": ["Select Finder/Monitor"], "to": "VF(Manual)", "set": {0x049c: 1, 0x047a: 6},
     "walk": ["Viewfinder Bright.", "Finder Color Temp.", "Finder Frame Rate"], "scan": "kit2_page_scan_osd",
     "run": "kit2_pass3_finder", "prove_eyes": "osd-all",
     "context": "HDMI Info. Display Off, Select Finder/Monitor VF(Manual)"},
    # Auto Framing Settings > Framing Oper. Mode answers a notice with Auto Framing Off, and with it On
    # "not available as follows: Recognition Target Auto" (2026-10-31), so Human (1) is set too.
    # Auto Framing On blanks HDMI, so it runs over the OSD (CAMSET_EYES=osd, the OSD movie scan)
    {"name": "Movie Auto Framing", "row": ["Auto Framing Settings", "Auto Framing"], "to": "On",
     "map": "kit2_crawl_movie/map.json", "set": {0x116e: 0, 0x03a7: 1},
     "walk": ["Auto Framing Settings"], "scan": "kit2_page_scan_movie_dm_osd", "prove_eyes": "osd-all",
     "run": "kit2_pass3_autoframe2", "context": "Movie mode, Auto Framing On, Recognition Target Human",
     "rows": ["Auto Framing Settings > Framing Oper. Mode"]},
    # Proxy Rec. Settings is greyed with Proxy Recording Off (2026-10-31)
    {"name": "Movie Proxy", "row": ["Proxy Settings", "Proxy Recording"], "to": "On",
     "map": "kit2_crawl_movie/map.json", "set": {0x0280: 0, 0x0282: 0},
     "walk": ["Proxy Settings"], "scan": "kit2_page_scan_movie_dm",
     "run": "kit2_pass3_proxy", "context": "Movie mode, Proxy Recording On, Proxy File Format XAVC HS HD"},
    # S&Q's Record Setting at another Rec Frame Rate: does 0x0254 move? (2026-10-31)
    {"name": "S&Q 24p", "row": ["S&Q Settings", "Frame Rate Settings", "Rec Frame Rate"], "to": "24p",
     "map": "kit2_crawl_movie/map.json", "set": {0x0240: 4},
     "walk": ["S&Q Settings"], "scan": "kit2_page_scan_movie_dm", "run": "kit2_pass3_sq24",
     "context": "Movie mode, S&Q Rec Frame Rate 24p", "rows": ["S&Q Settings > Record Setting"]},
    {"row": ["Recognition Target"], "to": "Human", "set": {0x03a7: 1},
     "walk": ["Face Priority in Mul...", "Soft Skin Effect", "Right/Left Eye Select", "Regist. Face Priority"]},
]


def labels_of(path, mp=None) -> tuple:
    for r in read_json(RUN_ROOT / mp if mp else PASS1 / "map_all.json")["rows"]:
        if r["path"] == path:
            by = {}
            for o in r["options"]:
                by.setdefault(o["index"], o["label"])
            return [by[i] for i in sorted(by)], r["kind"]
    raise SystemExit(f"{path} is not in pass 1's map")


def switch(link, hdmi, run, cycle, model, b) -> None:
    """Choose b["to"] on b["row"] and OK, as a proof would; leaves the shooting screen up."""
    # a blocker can give the list as this state shows it (XAVC HS 4K offers 60p, 24p, 120p: no 30p)
    labels, kind = (b["labels"], "list") if b.get("labels") else labels_of(b["row"], b.get("map"))
    cam = LiveCamera(link, hdmi, run)
    cam.press("menu")
    j = next((i for i, p in enumerate(cycle) if same_position(cam.read(), p["screen"])), None)
    if j is None or go_to(cam, cycle, model, j, b["row"][0]) is None:
        raise Failed(f"could not reach {b['row'][0]!r} by the scan")
    enter_any(cam, b["row"], 0)
    cam.press("right")
    if cam.read().kind != kind:
        raise Failed(f"Right on {b['row']} opened {cam.read().kind}, not a {kind}")
    cur = option_index(cam, labels, kind)
    target = [i for i, l in enumerate(labels) if option_key(main_name(l, kind)) == option_key(main_name(b["to"], kind))]
    if cur is None or len(target) != 1:
        raise Failed(f"{b['row']}: on option {cur}, target {b['to']!r} matches {target}")
    move_to(cam, cur, target[0], len(labels), kind)
    if option_index(cam, labels, kind) != target[0]:
        raise Failed(f"{b['row']}: the cursor is not on {b['to']!r}")
    cam.press("enter")
    if cam.read().kind == "notice":
        cam.press("menu")
    cam.cancel_to_menu()
    to_shooting(link, hdmi, "after the switch")


# Why a blocker switched by a file is refused, and what to do instead (docs/decisions/0006)
RETIRED = ("switching by a file is retired: it writes values into a settings file and uploads it, and only files the "
           "camera wrote are uploaded (docs/decisions/0006; a hand-edited file boot-looped the a1 II on 2026-11-01). "
           "Instead: change the setting on the camera (the menu, or the owner by hand), watch it take, download that "
           "state, and prove from it with kit/prove_run.py --start FILE")


def file_switch(link, start: Path, values: dict) -> Path:
    """Retired (decision 6): the start file with values written in would be a file no camera wrote. Refuses, and
    writes and uploads nothing."""
    raise Failed(f"{[f'0x{r:04x}' for r in values]}: {RETIRED}")


def restore(run, start: Path) -> int:
    """Put the start file back if anything differs from it; the records that still differ."""
    hdmi, ending = eyes_from_config(run), None
    try:
        with restoring("pass 3's restore"), Link(run) as link:      # a link that will not open is exit 4 too
            hdmi.attach(link)
            ending = end_session(link, hdmi, start, "the restore", tag="p3-end")
    finally:
        hdmi.close()
    n = session.check_restore(run, ending, start)
    print(f"   after the restore: {n} records differ", flush=True)
    return n


def step(args: list, log) -> int:
    print("  $ " + " ".join(args[1:]), flush=True)
    # each step works on this run's camera, whatever named it (camkit.paths)
    env = {**os.environ, "PYTHONUTF8": "1", paths.ENV: RUN_ROOT.name}
    r = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, env=env)
    return r.returncode


def selected(only) -> list:
    """The blockers to run: those --only names (by "name", else the first label of their row), else every one not
    marked "on_request"."""
    return [b for b in BLOCKERS
            if not ((only and b.get("name", b["row"][0]) not in only) or (b.get("on_request") and not only))]


def enter_state(link, hdmi, run, cycle, model, b) -> None:
    """Into the blocker's state: each of its "first" states chosen in the menu, in order (a File Format before that
    format's Rec Frame Rate), then its own switch. The final restore puts all of them back: it uploads the start file
    downloaded before the first."""
    for pre in b.get("first", []):
        switch(link, hdmi, run, cycle, model, pre)
        time.sleep(1)
    switch(link, hdmi, run, cycle, model, b)
    time.sleep(1)


def walk_and_prove(b, log) -> int:
    """A blocker's rows walked and proved in its state, each a step of its own (kit/crawl_run.py one row per
    "walk"; the labels, kit/pass1_labels.py; the third reader, kit/tiebreak.py, for the options the first two read
    differently, whose failure stops nothing: the map lists what stays unresolved; the run's own map, kit/pass1_map.py
    --own, so pass 1's map_all.json is not touched; kit/prove_run.py over that map). A blocker may walk with another
    scan into a run folder of its own (Movie mode's file formats, 2026-10-30) and name the rows to prove: --rows
    proves every option again. The exit of the first walk, labels or map step that failed (no proof then), else 0."""
    folder = RUN_ROOT / b.get("run", P3.name)
    scan_args = ["--scan", str(RUN_ROOT / b["scan"])] if b.get("scan") else []
    rc = 0
    for row in [b["walk"]] if isinstance(b["walk"], str) else b["walk"]:
        rc = rc or step([PY, "-u", "kit/crawl_run.py", "--run", folder.name, "--start-label", row,
                         "--limit", "1"] + scan_args, log)
    rc = rc or step([PY, "kit/pass1_labels.py", str(folder)], log)
    if rc == 0:
        step([PY, "-u", "kit/tiebreak.py", str(folder)], log)
    rc = rc or step([PY, "kit/pass1_map.py", "--own", str(folder)], log)
    if rc == 0:
        args = [PY, "-u", "kit/prove_run.py", "--map", str(folder / "map.json"), "--retry-failed"] + scan_args
        args += ["--context", b["context"]] if b.get("context") else []
        args += ["--eyes", b["prove_eyes"]] if b.get("prove_eyes") else []
        for row in b.get("rows", []):
            args += ["--rows", row]
        step(args, log)
    return rc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", action="append", default=None,
                    help="blocker rows to do (by their name, else their first label)")
    add_scan_argument(ap)
    a = ap.parse_args()
    body = models.current()
    if body != models.A1II:
        sys.exit(f"the blocker table is the {models.A1II}'s (firmware 4.00); this camera is "
                 f"{body or 'not known yet'}: write its own from its pass 1's greyed rows first")
    cycle, model = load_scan(a.scan)
    chosen = selected(a.only)
    by_file = [b.get("name", " > ".join(b["row"])) for b in chosen if b.get("set")]
    if by_file:
        print(f"refused, {len(by_file)} blockers switched by a file ({', '.join(by_file[:6])}"
              f"{', ...' if len(by_file) > 6 else ''}): {RETIRED}", flush=True)
    chosen = [b for b in chosen if not b.get("set")]
    if not chosen:
        sys.exit("nothing to run: " + RETIRED)
    check_readers()     # no reader listed: stop before the link opens, nothing pressed
    run = Run("kit2_pass3")
    with open(P3 / "pass3.log", "a", encoding="utf-8") as log:
        restored = run_blockers(run, cycle, model, chosen, log)
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


def run_blockers(run, cycle, model, chosen, log) -> bool:
    """Each blocker in turn: into its state (enter_state), its rows walked and proved there, the start file back on.
    Stops at the first restore that does not check out, and then returns False; True when the camera is as the last
    blocker's start file at the end (a STOP included, once its restore checked out)."""
    for b in chosen:
        name = " > ".join(b["row"]) + f" = {b['to']}"
        print(f"== {name}: " + (f"walk {b['walk']!r}" if b.get("walk") else f"prove {b['prove']}"), flush=True)
        hdmi = eyes_from_config(run)
        start, stopped = None, False
        try:
            with Link(run) as link:
                hdmi.attach(link)
                to_shooting(link, hdmi, "the start download")
                start = link.download("p3-start")
                time.sleep(5)
                # a blocker made for one state (Movie grid: a File Format loaded first) checks it is in it
                cs = camset.read(start)
                if cs.model != models.A1II:
                    raise SystemExit(f"the camera is a {cs.model}: the blocker table is the {models.A1II}'s")
                off = {f"0x{rid:04x}": cs.get(0, rid).value() for rid, v in b.get("expect", {}).items() if cs.get(0, rid).value() != v}
                if off:
                    raise Failed(f"not in the state this blocker is for: {off}")
                try:
                    enter_state(link, hdmi, run, cycle, model, b)
                except StopRequested:
                    # a STOP file (or a first Ctrl-C) at a press of the switch: close what it opened with cleanup
                    # presses before the link closes, since a dropped session applies the dialog on screen
                    stopped = True
                    print("   STOP file: cancelling the switch", flush=True)
                    try:
                        to_shooting(link, hdmi, "the cancel after a stop")
                    except Exception as e:
                        print(f"   the cancel: {type(e).__name__}: {e}", flush=True)
                    raise
                switched = link.download("p3-switched")
                ch = camset.diff(camset.read(start), camset.read(switched))
                print(f"   switched: {[(c.key, c.before, c.after) for c in ch][:6]}", flush=True)
        except (Failed, LinkError, RuntimeError, StopRequested) as e:
            # whatever part of the switch applied goes back before the next blocker (decision 15): a blocker's "first"
            # state chosen before its own switch failed, a choice made before to_shooting gave up, the capture dongle
            # gone after 24p reached HDMI, a download refused after the switch. restore() uploads the start file only
            # when something differs from it; if that fails too, stop and leave it to the caller's upload
            print(f"   the switch {'stopped' if stopped else 'failed'}: {e}", flush=True)
            hdmi.close()
            if start is None:               # nothing was downloaded, so nothing was switched
                if stopped:
                    break
                continue
            try:
                if restore(run, start) == 0:
                    if stopped:
                        print("stopping, as the STOP file asks: the start file is back on", flush=True)
                        break
                    continue
            except Exception as e2:
                print(f"   the restore failed too: {e2}", flush=True)
            print("stopping: the camera may still be switched", flush=True)
            return False
        hdmi.close()
        time.sleep(3)
        if b.get("prove"):                  # rows already mapped: prove them again in the switched state
            args = [PY, "-u", "kit/prove_run.py", "--context", b["context"]]
            for row in b["prove"]:
                args += ["--rows", row]
            step(args, log)
        else:
            rc = walk_and_prove(b, log)
            if rc != 0:
                print(f"   the walk or the labels failed (exit {rc}); see {P3 / 'pass3.log'}", flush=True)
        time.sleep(3)
        if restore(run, start) != 0:
            print("the restore did not check out: stopping", flush=True)
            return False
    return True


if __name__ == "__main__":
    main()
