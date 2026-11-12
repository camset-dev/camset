"""Page scan (pass 1, part 1): every top-level menu row, with Down only, watched over HDMI.

    .venv/bin/python -u kit/page_scan.py --mode Stills [--max N] [--run kit2_page_scan]
    .venv/bin/python -u kit/page_scan.py --mode Movie --run kit2_page_scan_movie

Presses only MENU (open at the start, close at the end), Down, and Right when the pixels show the
cursor in the group column (it steps into the rows). Never Enter. Before every press the screen must
be a menu page with the cursor on the rows or the Main tile grid; anything else stops the scan without
pressing. After every press the move is checked: the next row on the same page, or the first row of
a new page (new pages get a second, longer look: they redraw more slowly). The scan ends when its
first screen comes round again (exact pixel signature: row labels repeat across pages, so text is
not used), on a STOP file (<run>/STOP in the camera's runs/<model>_fw<fw>/), or after --max presses.

Nothing is pressed while the menu is still sliding in or across (a frame caught mid-slide reads as a menu with no
focus; the scan looks again until it stops): a Right sent to a moving menu landed on the Drive Mode row and opened
it, 2026-11-06. The settings are downloaded before the first press and, if anything differs at the end, the start
file goes back on and the restore is checked.
Writes runs/<model>_fw<fw>/<run>/scan.jsonl and, after a full lap, scan_rekeyed.json (the cycle later steps use), one line per settled screen: the frame, kind, page key (a
hash of the breadcrumb bar), cursor row, row states (normal / greyed / cursor) and timing.
Labels and values are read afterwards from the saved frames (VLM pool / OCR), off the camera loop.
--mode names the shooting mode the camera is in (Stills, Movie, S&Q: the menus differ per mode), which the
scan records in <run>/scan_mode.json before its first press, as unfinished, and marks whole once its full lap is
written (runner.record_mode, runner.mark_lap_whole): a runner takes by default only the latest whole scan of the mode
it works in whose page model is newer than its lap (runner.latest_scan). The camera's mode is not read here: say the
one it is in. A run folder that holds a lap or page model of a scan recording no mode or another one is refused before
anything is sent (scan into a new --run, or record the old scan's mode with kit/page_model.py --mode first); a folder
whose scan records the same mode is scanned again, and is no default until the new lap is whole: the scan's id, in its
record and in each of its records in scan.jsonl, keeps an earlier scan's records out of the new lap. A scan made while a
kept kit/provers/mode_switch.py switch left the camera in Intelligent Auto records it, and is taken by default only
while such a switch waits (runner.AUTO).
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import jsonl, paths, screen  # noqa: E402
from camkit.frames import eyes_from_config  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.runs import Run  # noqa: E402
from prove_run import LOCK_S, to_shooting  # noqa: E402
from runner import (EXIT_UNRESTORED, LATEST_SCAN, SCAN_ID, SCAN_MODES, end_session, mark_lap_whole,  # noqa: E402
                    record_mode, recorded_mode, refuse_switched, restore_checked, scan_mode, scan_record,
                    switch_for_scan, write_json)


def page_key(f) -> str:
    """The breadcrumb bar as a coarse picture plus the n/N counter at a finer one: one key per page.
    (At the coarse size alone "5/65" and "6/65" were the same picture: two pages share the breadcrumb
    "Shooting > Image Quality/Rec", 2026-10-28.) On the Main tile page the breadcrumb names the tile."""
    g = screen._grey(f.image)
    return screen._hash(screen._binarize_small(g, (0, 0, 520, 40), (65, 6)),
                        screen._binarize_small(g, (520, 0, 640, 40), (60, 20)))


class Scan:
    def __init__(self, run, link, hdmi, max_presses):
        self.run, self.link, self.hdmi, self.max = run, link, hdmi, max_presses
        self.out = run.dir / "scan.jsonl"             # one line per settled screen, appended as it is seen
        self.presses = 0
        # this scan's id, as its record holds it (runner.record_mode): each of its records carries it (write_cycle)
        self.scan_id = scan_record(run.dir).get(SCAN_ID)

    def press(self, button, before, tag):
        t = time.monotonic()
        # the screen the press is made on goes with it: on the shooting screen only MENU goes out (decision 21)
        self.link.press(button, screen=screen.read(before))
        self.presses += 1
        f, moved = self.hdmi.settle(before, tag, expect_change=True, sent_at=t)
        timing = dict(self.hdmi.timing)
        return f, moved, timing

    def at_rest(self, f, s, tag):
        """A menu page caught while it slides (opening, or a page change) reads as a menu with no focus: look
        again, longer, until it stops. Nothing is pressed from a moving menu (2026-11-06: a mid-slide frame read
        as the group column, and the Right meant to step into the rows opened the Drive Mode row instead)."""
        for _ in range(3):
            if not (s.kind == "menu" and s.focus is None):
                break
            f, _ = self.hdmi.settle(f, tag, expect_change=False, quiet=0.5, timeout=3.0)
            s = screen.read(f)
        return f, s

    def record(self, f, s, **extra):
        rec = {"n": self.presses, "frame": f.path.name, "kind": s.kind, "page": page_key(f), "focus": s.focus,
               "row": s.row, "col": s.field, "rows": s.count, "slots": s.slots, "signature": s.signature,
               **({"scan": self.scan_id} if self.scan_id else {}), **extra}
        jsonl.append(self.out, rec)
        return rec

    def run_scan(self):
        f = self.hdmi.grab("start")
        s = screen.read(f)
        print(f"start: {s.kind}", flush=True)
        if s.kind == "shooting":
            f, _, timing = self.press("menu", f, "menu-open")
            s = screen.read(f)
            print(f"MENU -> {s.kind} focus {s.focus} ({timing})", flush=True)
        f, s = self.at_rest(f, s, "menu-rest")
        if s.kind == "menu" and s.focus == "groups":
            f, _, _ = self.press("right", f, "into-rows")
            s = screen.read(f)
            f, s = self.at_rest(f, s, "rows-rest")
        if not ok_to_press(s):
            print(f"STOPPED before scanning: screen is {s.kind} (focus {s.focus}); nothing more pressed", flush=True)
            return
        first = (page_key(f), s.signature)
        self.record(f, s, start=True)
        seen = {}
        pages = {page_key(f)}
        while self.presses < self.max:
            if self.run.stop_requested():
                print("STOP file seen", flush=True)
                break
            prev_f, prev_s, prev_page = f, s, page_key(f)
            f, moved, timing = self.press("down", prev_f, "down")
            s = screen.read(f)
            f, s = self.at_rest(f, s, "down-rest")
            page = page_key(f)
            if not moved:
                print(f"  Down changed nothing after {self.presses} presses; stopping", flush=True)
                break
            new_page = page != prev_page
            if new_page:
                # page changes redraw more slowly: look again with a longer quiet window
                f2, later = self.hdmi.settle(f, "down-late", expect_change=False, quiet=0.3, timeout=2.0)
                if later:
                    f, s, page = f2, screen.read(f2), page_key(f2)
                pages.add(page)
            expected = (s.kind == "tiles" or prev_s.kind == "tiles" or
                        (new_page and s.row == 0) or (not new_page and s.row == (prev_s.row or 0) + 1))
            self.record(f, s, new_page=new_page, expected=expected, timing=timing)
            note = "" if expected else "   <- unexpected move"
            print(f"{self.presses:4d} {s.kind:6s} page {page[:6]} row {s.row} of {s.count} "
                  f"{'NEW PAGE ' if new_page else ''}{timing.get('moved')}s{note}", flush=True)
            if (page, s.signature) == first:
                print(f"LAP complete: {self.presses} presses, {len(pages)} pages", flush=True)
                break
            key = (page, s.signature)
            seen[key] = seen.get(key, 0) + 1
            if seen[key] > 2:
                print(f"  the same screen came back {seen[key]} times without a lap; stopping", flush=True)
                break
            if not ok_to_press(s):
                # close() presses MENU only on a menu page or the Main tiles, never on a dialog (that
                # is left for a hand at the camera)
                print(f"  screen is {s.kind} (focus {s.focus}); stopping without pressing Down", flush=True)
                break
        self.close()

    def close(self):
        f = self.hdmi.grab("before-close")
        s = screen.read(f)
        if s.kind in ("menu", "tiles"):
            f, _, _ = self.press("menu", f, "menu-close")
            print(f"MENU -> {screen.read(f).kind}", flush=True)


def after_download(hdmi, done_at: float):
    """The camera shows "Saving to the connected device..." for a moment after a download returns, and MENU within
    LOCK_S of it is ignored (a MENU into the notice, 2026-11-06): wait for the shooting screen and the lock."""
    while True:
        s = screen.read(hdmi.grab("after-download", save=False))
        waited = time.monotonic() - done_at
        if waited > LOCK_S and s.kind == "shooting":
            return
        if waited > 25:
            raise SystemExit(f"after the download the camera stayed on a {s.kind} screen; nothing pressed")
        time.sleep(0.4)


def ok_to_press(s) -> bool:
    return (s.kind == "menu" and s.focus == "rows") or s.kind == "tiles"


def write_cycle(d: Path) -> bool:
    """scan_rekeyed.json, the cycle every later step navigates by: this scan's records in order (those of scan.jsonl
    that carry the scan's id, runner.SCAN_ID in its record: a scan made again in the same folder appends to it), once a
    full lap came round (its last record is the first again), and the scan's record marked whole with the lap's id
    (runner.mark_lap_whole). A scan with no record of its own (stopped before its first) or an unfinished one writes
    nothing, and its record stays unfinished: no runner takes it by default (runner.scan_unready), and no lap of an
    earlier scan is written again in its name."""
    scan_id = scan_record(d).get(SCAN_ID)
    recs = [r for r in jsonl.read(d / "scan.jsonl") if scan_id and r.get("scan") == scan_id]
    if not recs:
        print("this scan recorded no screen: no cycle file written (scan again); no runner takes this scan by default",
              flush=True)
        return False
    starts = [i for i, r in enumerate(recs) if r.get("start")]
    recs = recs[starts[-1]:] if starts else recs
    if len(recs) > 2 and (recs[-1]["page"], recs[-1]["signature"]) == (recs[0]["page"], recs[0]["signature"]):
        write_json(d / "scan_rekeyed.json", recs, indent=0)
        mark_lap_whole(d, scan_id)
        print(f"cycle written: {d / 'scan_rekeyed.json'} ({len(recs) - 1} positions); build its page model next "
              f"(kit/page_model.py --vlm {d.name}): no runner takes the scan by default before it", flush=True)
        return True
    print("no full lap: no cycle file written (scan again); no runner takes this scan by default", flush=True)
    return False


def refuse_folder(d: Path, mode: str) -> None:
    """Stops before anything is sent when the run folder holds a lap or a page model of a scan that records no mode
    or another one: the scan would label that one as `mode` (2026-11-11). A folder whose scan records `mode` may be
    scanned again; a folder named LATEST_SCAN could never be named with --scan."""
    from camkit import paths
    if d.name == LATEST_SCAN:
        sys.exit(f"page_scan: --run {LATEST_SCAN}: --scan {LATEST_SCAN} means the latest page scan of a mode, so a scan "
                 "of that name could never be named; give the run another name. Nothing was sent to the camera.")
    held = [n for n in ("scan_rekeyed.json", "model.json") if (d / n).exists()]
    had = recorded_mode(d)
    if held and had != mode:
        what = f"records {had} mode" if had else "records no mode"
        sys.exit(f"page_scan: {paths.shown(d)} holds a page scan already ({', '.join(held)}) that {what}, and this "
                 f"scan is of the {mode} mode menu: scanning into it would label that scan as {mode}. Nothing was "
                 f"sent to the camera. Use a new --run, or, if you know the mode the old scan was made in, record it "
                 f"first with .venv/bin/python kit/page_model.py --mode <Stills|Movie|S&Q> {d.name}.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=600, help="press limit")
    ap.add_argument("--run", default="kit2_page_scan",
                    help="run folder in the camera's runs/<model>_fw<fw>/ (Movie mode has a menu of its own: "
                         "kit2_page_scan_movie)")
    ap.add_argument("--mode", required=True, type=scan_mode,
                    help=f"the shooting mode the camera is in now, whose menu this scans ({', '.join(SCAN_MODES)}); "
                         "recorded in the scan, by which the runners take it")
    a = ap.parse_args()
    refuse_folder(paths.run_root() / a.run, a.mode)
    refuse_switched(a.mode)                   # the kit's own record says the camera was left in another mode
    run = Run(a.run)
    try:
        # before anything is sent: a runner takes the scan by its mode, once its lap is whole (runner.scan_unready),
        # and a scan made while a kept switch left the camera in Intelligent Auto as that menu's (runner.scan_auto)
        record_mode(run.dir, a.mode, scanning=True, switch=switch_for_scan(a.mode))
    except ValueError as e:
        sys.exit(f"page_scan: {e}")
    hdmi = eyes_from_config(run)
    start, ending = None, None
    try:
        with Link(run) as link:
            hdmi.attach(link)
            # the scan presses only Down and one Right, but a press sent while the menu slides lands where the cursor
            # really is (Drive Mode opened and moved, 2026-11-06): the settings are downloaded first and go back on
            # at the end if anything moved
            to_shooting(link, hdmi, "the start download")
            start = link.download("before")
            after_download(hdmi, time.monotonic())
            t0 = time.monotonic()
            try:
                Scan(run, link, hdmi, a.max).run_scan()
            except Exception as e:                  # a STOP at a press, a dropped link, the eyes' feed: restore all the same
                print(f"the scan stopped: {type(e).__name__}: {e}", flush=True)
            print(f"done in {time.monotonic() - t0:.0f} s", flush=True)
            write_cycle(run.dir)
            # never disconnect with anything open: MENU cancels whatever the scan stopped on (never Enter), and a
            # dropped session could otherwise apply an open dialog
            ending = end_session(link, hdmi, start, "the end of the scan")
        restored = restore_checked(run, ending, start)
    finally:
        hdmi.close()
    if not restored:
        sys.exit(EXIT_UNRESTORED)            # the camera is not known to be as the start file (runner)


if __name__ == "__main__":
    main()
