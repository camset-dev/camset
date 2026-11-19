"""Measure on the camera how soon a press's screen settles and how soon the menu's lock after a download ends, so that
the settle's windows (camkit.frames: HDMI_QUIET, HDMI_NOTHING, OSD_QUIET, OSD_LATE) and the lock's rule
(camkit.session.lock_over) are set from numbers, never from an estimate (the speed review of 2026-11-18: its items 8
and 11, its measurements 5.1, 5.4 and 5.5; the owner's question of 2026-11-19 for OSD eyes). Nothing it presses chooses
anything; it changes no setting of the kit's.

    .venv/bin/python -u kit/tools/settle_probe.py presses [--path ROW ...] [--count 200] [--hold 2.0] [--keys up,down]
    .venv/bin/python -u kit/tools/settle_probe.py lock [--delays 1.6,2.0,2.4,2.8,3.2] [--trials 5] [--after-notice]
    CAMSET_EYES=osd .venv/bin/python -u kit/tools/settle_probe.py presses     # the camera's own picture over the link

presses: from the menu (one MENU from the shooting screen, camkit.live.menu_from_shooting; --path walks to a row
first, Right only into submenus, as the provers walk: prove_run.enter_any, and only where this body has been seen to
open each row above the last, else it stops before anything connects, as drive.py does: drive.first_open_or_exit),
`--count` presses of `--keys` in turn, each through camkit.live.LiveCamera (the screen read and judged before it,
every guard of a run). Up and Down move a menu page's or a submenu's cursor and choose nothing; "left-right" presses
Left, then Right only once a reading taken just before it shows a menu page with its focus in the group column (Right
leaves the groups for the rows, opening nothing; a screen that does not read so stops the run before Right). Every
frame the eyes give while the press settles, and for `--hold` s after the kit's own
settle has ended (a change the kit would have missed), is looked at: when the picture first and last changed after the
press went out (camlink's command, Link.press), by key and by the screen kind before it; the frames either side of
every change later than LATE_KEPT are kept in the run's late/ folder (a slow redraw, a scroll bar, a blinking mark);
and before each press two frames in a row are compared (5.5: whether a still menu's frames are alike, which a fresh
look before Right would need).

lock: from the shooting screen, a settings download, then MENU `--delays` s after its reply (with --after-notice, that
long after the first frame read as the shooting screen after the saving notice), `--trials` times each, as
kit2_speed_lock measured HDMI eyes on 2026-11-18: whether a menu page showed within MENU_SEEN s, what the frames showed
before. A MENU that opened the menu is closed with MENU on the menu page; one that did not gets no second MENU (the
shooting screen is waited for, and the next trial starts).

Either way the run starts from the camera's file and ends restoring it (runner.prover_session), writes one line per
press or trial (probe.jsonl) and a table (probe_table.txt, printed too) naming the eyes and the connection, "lan" or
"usb" (a USB run told from a LAN run later; nothing else of the address)."""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import frames, screen, session  # noqa: E402  (camkit first: it says so when the venv is not the one used)
from camkit.frames import eyes_from_config, keep  # noqa: E402
from camkit.runs import Run  # noqa: E402
import numpy as np  # noqa: E402

LATE_KEPT = 0.3         # s after the press: a change later than this keeps the frames either side of it
MENU_SEEN = 3.0         # s a MENU's menu page is watched for (the OSD picture lags the screen)
KEYS = ("up", "down", "left-right")
MENU_KINDS = ("menu", "submenu", "tiles")       # the screens whose sight says a MENU opened the menu
POLL = {"hdmi": 0.005, "osd": 0.04}     # s between looks while watching (the kit's own settle polls so)


class Watch:
    """Every frame the eyes give (HDMI: latest(); OSD: peek()), the kit's own settle's among them, noted with when it
    came (HDMI: its capture time; OSD: its fetch) while a press is watched: each change from the frame before, with
    both frames, for press_row."""

    def __init__(self, eyes, clock=time):
        self.eyes, self.clock, self.osd = eyes, clock, getattr(eyes, "name", "") == "osd"
        self.steady = None
        self.changes, self.last = [], None
        name = "peek" if self.osd else "latest"
        real = getattr(eyes, name)

        def looked(*a, **k):
            f = real(*a, **k)
            if f is not None:
                self.see(f)
            return f
        setattr(eyes, name, looked)
        self.look = looked

    def mark(self, steady=None) -> None:
        """From now on: no change noted yet (the frame before the press is the next one seen)."""
        self.changes, self.last, self.steady = [], None, steady

    def see(self, f) -> None:
        t = getattr(f, "t", None) if not self.osd else None
        t = t if isinstance(t, (int, float)) and t > 0 else self.clock.monotonic()
        if self.last is not None and not self.osd and t == self.last[0]:
            return                                      # the same HDMI frame looked at twice
        if self.last is not None and self.differs(self.last[1], f):
            self.changes.append((t, self.last[1], f))
        self.last = (t, f)

    def differs(self, a, b) -> bool:
        if self.osd:
            return not frames.same(a, b, frames.OsdSource.TOL)
        sa = getattr(a, "small", None)
        sb = getattr(b, "small", None)
        sa = sa if sa is not None else frames._small(a.image)
        sb = sb if sb is not None else frames._small(b.image)
        moved = np.abs(np.asarray(sa, float) - np.asarray(sb, float)) > 6.0
        if self.steady is not None:
            moved &= self.steady
        return float(moved.mean()) > frames.HdmiSource.TOL


def press_row(watch: Watch, sent: float, key: str, before: str, after: str, keep_in: Path | None, n: int) -> dict:
    """One press's line: when the picture first and last changed after it went out (`sent`), how many changes, and the
    frames either side of each change later than LATE_KEPT kept in `keep_in` (their names)."""
    after_sent = [(t - sent, a, b) for t, a, b in watch.changes if t >= sent]
    kept = []
    for dt, a, b in after_sent:
        if dt > LATE_KEPT and keep_in is not None:
            for side, f in (("before", a), ("after", b)):
                name = f"{n:04d}_{key}_{dt:.2f}s_{side}.png"
                keep(f, keep_in / name, False)
                kept.append(name)
    return {"press": n, "key": key, "kind_before": before, "kind_after": after,
            "first": round(after_sent[0][0], 3) if after_sent else None,
            "last": round(after_sent[-1][0], 3) if after_sent else None, "changes": len(after_sent),
            **({"late_kept": kept} if kept else {})}


def still_pair(eyes, clock=time) -> dict:
    """Two frames in a row of the screen as it stands (HDMI: two captures; OSD: two fetches POLL apart): whether they are
    alike, pixel for pixel, and the share of 8x8 blocks apart (5.5)."""
    a = eyes.grab("still", save=False)
    for _ in range(200):
        clock.sleep(POLL.get(getattr(eyes, "name", ""), 0.04))
        b = eyes.grab("still", save=False)
        if getattr(eyes, "name", "") == "osd" or getattr(b, "t", None) != getattr(a, "t", None):
            break
    same = bool(np.array_equal(a.image, b.image))
    share = float((np.abs(frames._small(a.image) - frames._small(b.image)) > 6.0).mean())
    return {"still_identical": same, "still_share": round(share, 5)}


def probe_presses(cam, link, eyes, run, keys, count: int, hold: float, clock=time) -> list:
    """`count` presses of `keys` in turn (see the module's docstring), each watched; returns their lines."""
    watch = Watch(eyes, clock)
    sent_at = []
    real_press = link.press

    def press(*a, **k):
        sent_at.append(clock.monotonic())
        return real_press(*a, **k)
    link.press = press
    late = run.dir / "late"
    late.mkdir(parents=True, exist_ok=True)
    rows, n = [], 0
    for i in range(count):
        if run.stop_requested():
            print("STOP file: no more presses", flush=True)
            break
        for key in (["left", "right"] if keys[i % len(keys)] == "left-right" else [keys[i % len(keys)]]):
            if key == "right":
                # read afresh just before it, never the reading the settle left (a mid-slide frame, or the late redraw
                # this probe looks for, can read as the groups while the rows are focused, and Right opens a row)
                now = cam.refresh("before-right")
                if now.kind != "menu" or getattr(now, "focus", None) != "groups":
                    raise RuntimeError(f"Right goes only from the group column, and the screen read just before it is "
                                       f"a {now.kind} page, its focus {getattr(now, 'focus', None)!r} "
                                       f"({cam.frame.path.name}): no Right")
            n += 1
            still = still_pair(eyes, clock)
            before = cam.read().kind
            noisy = getattr(eyes, "noisy", None)
            watch.mark(~noisy(clock.monotonic()) if callable(noisy) and not watch.osd else None)
            watch.look()                                # the frame before the press
            cam.press(key)
            sent = sent_at[-1] if sent_at else clock.monotonic()
            end = clock.monotonic() + hold
            while clock.monotonic() < end:              # past the kit's own settle: a later change is seen too
                clock.sleep(POLL.get(getattr(eyes, "name", ""), 0.04))
                watch.look()
            row = {**press_row(watch, sent, key, before, cam.read().kind, late, n), **still,
                   "kit_timing": getattr(eyes, "timing", None) or None}
            rows.append(row)
            jsonl_append(run.dir / "probe.jsonl", row)
            print(f"{n:4d} {key:5s} {before:8s} first {row['first']} last {row['last']} changes {row['changes']}"
                  + (f"  kept {len(row.get('late_kept', []))} frames" if row.get("late_kept") else ""), flush=True)
    return rows


def probe_lock(cam, link, eyes, run, delays, trials: int, after_notice: bool = False, clock=time) -> list:
    """MENU at each delay after a download, `trials` times each (see the module's docstring); returns the lines."""
    from runner import close_screen
    rows = []
    for delay in delays:
        for trial in range(trials):
            if run.stop_requested():
                print("STOP file: no more trials", flush=True)
                return rows
            session.wait_for(eyes, ("shooting",), "the trial's download", link=link)
            t0 = clock.monotonic()
            link.download(f"lock-{delay:g}-{trial}")
            done = clock.monotonic()
            seen, notice_gone = [], None
            while True:
                kind = screen.read(eyes.grab("lock", save=False)).kind
                if not seen or seen[-1] != kind:
                    seen.append(kind)
                if notice_gone is None and kind == "shooting" and "notice" in seen:
                    notice_gone = clock.monotonic()
                since = notice_gone if after_notice else done
                if since is not None and clock.monotonic() - since >= delay:
                    break
                if clock.monotonic() - done > session.LOCK_NOTICE_LIMIT:
                    break                               # a notice that never goes: MENU as it stands
                clock.sleep(POLL.get(getattr(eyes, "name", ""), 0.04))
            cam.refresh("lock-before")
            before = cam.read().kind
            sent = clock.monotonic()
            cam.press("menu")                           # judged and settled as in any run (its menu_watch over HDMI)
            menu_after = 0.0 if cam.read().kind in MENU_KINDS else None
            while menu_after is None and clock.monotonic() - sent < MENU_SEEN:
                if screen.read(eyes.grab("lock", save=False)).kind in MENU_KINDS:
                    menu_after = clock.monotonic() - sent
                    break
                clock.sleep(POLL.get(getattr(eyes, "name", ""), 0.04))
            if menu_after == 0.0:                       # seen by the press's own settle: its time is the eyes' own
                menu_after = (getattr(eyes, "timing", None) or {}).get("moved") or clock.monotonic() - sent
            row = {"delay": delay, "trial": trial, "after_notice": after_notice, "download_s": round(done - t0, 3),
                   "sent_after_download": round(sent - done, 3),
                   "notice_gone_after_download": round(notice_gone - done, 3) if notice_gone else None,
                   "screen_before": before, "seen": seen, "opened": menu_after is not None,
                   "menu_after": round(menu_after, 3) if menu_after is not None else None}
            rows.append(row)
            jsonl_append(run.dir / "probe.jsonl", row)
            print(f"delay {delay:g} trial {trial}: MENU {row['sent_after_download']} s after the download on "
                  f"{before}: {'menu after ' + str(menu_after) + ' s' if menu_after is not None else 'no menu'}",
                  flush=True)
            if cam.refresh("lock-after").kind in MENU_KINDS:
                close_screen(cam, link)                 # a menu that opened, even late, closed with MENU on it
    return rows


def jsonl_append(path: Path, row: dict) -> None:
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(row) + "\n")


def centiles(xs: list) -> str:
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return "-"
    at = lambda q: xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]    # noqa: E731
    return f"{at(0.5):.2f}/{at(0.9):.2f}/{at(0.99):.2f}/{xs[-1]:.2f}"


def table(rows: list, mode: str, eyes: str, connection: str, scan_mode=None) -> str:
    """The run's table: for presses, by key and screen kind before it, the first and last change's median, 90th and
    99th centiles and maximum (s after the press went out), how many last changed later than 0.3, 0.5, 0.75 and 1.0 s,
    how many showed no change, and how many still pairs were alike; for the lock, by delay, how many MENUs opened the
    menu and how soon."""
    head = [f"settle_probe {mode}: eyes {eyes}, connection {connection}, shooting mode {scan_mode or 'not known'}",
            f"windows now: HDMI quiet {frames.HDMI_QUIET}, nothing {frames.HDMI_NOTHING}; OSD quiet {frames.OSD_QUIET},"
            f" late {frames.OSD_LATE}"]
    out = []
    if mode == "presses":
        out.append(f"{'key':6s} {'screen':9s} {'n':>4s}  {'first p50/p90/p99/max':24s} {'last p50/p90/p99/max':24s} "
                   f"{'>0.3':>5s} {'>0.5':>5s} {'>0.75':>5s} {'>1.0':>5s} {'none':>5s} {'alike':>6s}")
        groups = {}
        for r in rows:
            groups.setdefault((r["key"], r["kind_before"]), []).append(r)
        for (key, kind), rs in sorted(groups.items()):
            last = [r["last"] for r in rs]
            late = [sum(1 for x in last if x is not None and x > w) for w in (0.3, 0.5, 0.75, 1.0)]
            out.append(f"{key:6s} {kind:9s} {len(rs):4d}  {centiles([r['first'] for r in rs]):24s} "
                       f"{centiles(last):24s} " + " ".join(f"{x:5d}" for x in late)
                       + f" {sum(1 for x in last if x is None):5d} {sum(1 for r in rs if r.get('still_identical')):6d}")
    else:
        out.append(f"{'delay':>6s} {'n':>3s} {'menu':>5s}  {'menu after p50/p90/p99/max':28s} screens before")
        groups = {}
        for r in rows:
            groups.setdefault(r["delay"], []).append(r)
        for delay, rs in sorted(groups.items()):
            opened = [r["menu_after"] for r in rs if r["menu_after"] is not None]
            befores = ", ".join(sorted({r["screen_before"] for r in rs}))
            out.append(f"{delay:6g} {len(rs):3d} {len(opened):5d}  {centiles(opened):28s} {befores}")
    return "\n".join(head + out)


def connection_of(run) -> str:
    """"lan" or "usb" from the run's last link_open line (camlink's ready reply), nothing else of the address."""
    try:
        lines = (run.dir / "events.jsonl").read_text(encoding="utf-8").splitlines()
        opened = [json.loads(x) for x in lines if '"link_open"' in x]
        got = str((opened[-1].get("reply") or {}).get("connection") or "").split()[:1]
        return got[0] if got else "not said"
    except (OSError, ValueError, IndexError):
        return "not said"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("mode", choices=("presses", "lock"))
    ap.add_argument("--path", action="append", default=[], help="presses: the row to go to first, then its submenus")
    ap.add_argument("--keys", default="up,down", help=f"presses: the keys in turn, of {', '.join(KEYS)}")
    ap.add_argument("--count", type=int, default=200, help="presses: how many")
    ap.add_argument("--hold", type=float, default=2.0, help="presses: s watched after the kit's own settle ended")
    ap.add_argument("--delays", default="1.6,2.0,2.4,2.8,3.2", help="lock: s after the download, comma-separated")
    ap.add_argument("--trials", type=int, default=5, help="lock: trials per delay")
    ap.add_argument("--after-notice", action="store_true",
                    help="lock: the delays from the first frame read as the shooting screen after the saving notice")
    ap.add_argument("--run", default=None, help="run folder (default kit2_settle_presses or kit2_settle_lock)")
    from runner import add_scan_argument
    add_scan_argument(ap)
    a = ap.parse_args(argv)
    keys = [k.strip() for k in a.keys.split(",") if k.strip()]
    if any(k not in KEYS for k in keys) or not keys:
        sys.exit(f"--keys takes {', '.join(KEYS)}: nothing was sent to the camera")
    if a.mode == "presses" and a.path:
        # the walk opens each row above the last with Right: one this body has not been seen to open would be its first
        # open, which goes only under drive.py's procedure (camkit.first_open), so the probe stops here as drive.py does
        from types import SimpleNamespace

        from camkit import first_open
        from drive import first_open_or_exit
        first_open_or_exit(SimpleNamespace(path=a.path, press=[], owner=False), first_open.seen_record())
    delays = [float(x) for x in a.delays.split(",") if x.strip()]
    from runner import load_scan, prover_session
    cycle, model = load_scan(a.scan)            # the menu's map, and the shooting mode it was made in (session.MODE)
    run = Run(a.run or f"kit2_settle_{a.mode}")
    eyes = eyes_from_config(run)
    rows = []
    with prover_session(run, eyes, say_start=True, end_why="the settings download after the probe") as s:
        if a.mode == "presses":
            from camkit.live import menu_from_shooting
            from crawl_run import find_position, go_to
            from prove_run import enter_any
            menu_from_shooting(s.cam, tries=0)
            if a.path:
                j = find_position(s.cam, cycle, model)
                if j is None or go_to(s.cam, cycle, model, j, a.path[0]) is None:
                    raise RuntimeError(f"{a.path[0]!r} was not reached by the scan: nothing pressed on it")
                enter_any(s.cam, a.path, 0)
            rows = probe_presses(s.cam, s.link, eyes, run, keys, a.count, a.hold)
        else:
            rows = probe_lock(s.cam, s.link, eyes, run, delays, a.trials, a.after_notice)
        s.close()                                       # back to the shooting screen with cleanup presses
    text = table(rows, a.mode, getattr(eyes, "name", "?"), connection_of(run), session.MODE)
    (run.dir / "probe_table.txt").write_text(text + "\n", encoding="utf-8")
    print(text, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
