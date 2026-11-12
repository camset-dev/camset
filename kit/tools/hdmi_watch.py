"""Watch the camera over HDMI while the user drives it by hand; print what the pixel reader sees.

    .venv/bin/python -u kit/tools/hdmi_watch.py [--link] [--download] [--ocr] [--each] [--eyes osd]

Nothing is pressed. Every time the screen changes and settles, the frame is saved and one line is
printed: the screen type and the position fields the reader found (plus the title by OCR with --ocr).
--link keeps a remote session open (as during a walk: the exposure readouts blink); --download also
saves the settings file before and after and prints any difference, which should be none.
--each (2026-11-02, the owner changing by hand what the kit may not): every time an option screen
closes back to a menu page (or the shooting screen), the settings are downloaded and diffed against
the download before, written with the frames seen on the way to runs/<model>_fw<fw>/kit2_hdmi_watch/hand.jsonl. The
download closes the menu: the camera drops back to the shooting screen by itself. MENU within ~3 s of
a download is locked, so wait a few seconds before the next change.
--eyes osd watches the camera's own screen through the SDK instead: for rows greyed while HDMI is
connected (Touch Func. in Shooting, Finder Frame Rate), with the HDMI cable out.
--closed (with --each; 2026-11-02, rows the camera refuses while a remote session is open: Power Save
Start Time, the USB settings): no session while the owner changes things. Each return to the shooting
screen opens one, downloads, diffs and closes it again; wait for "READY" (the remote icon gone) before
the next change.

Stop with a STOP file in the run folder (runs/<model>_fw<fw>/kit2_hdmi_watch/STOP). Before the final download and
before disconnecting it waits for the shooting screen: a dropped session can apply an open dialog.
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# camkit before any other package, as in every kit program: a Python without the kit's packages is told so (camkit/start.py)
from camkit import camset, ocr, screen  # noqa: E402
from camkit.frames import HdmiSource, OsdFeed, _small  # noqa: E402
from camkit.link import Link, LinkError  # noqa: E402
from camkit.runs import Run  # noqa: E402
import numpy as np  # noqa: E402


def describe(s: screen.Screen) -> str:
    k = s.kind
    if k == "menu":
        return f"focus {s.focus} group {s.group} row {s.row}"
    if k == "submenu":
        return f"row {s.row}"
    if k in ("list", "sidelist"):
        saved = f" saved {s.current}" if k == "list" else ""
        return (f"cursor {s.row} of {s.count} visible{saved} scroll {s.scroll} "
                f"start {s.at_start} end {s.at_end} est {s.options_estimate}")
    if k == "dialog":
        on = sorted(g for g, v in s.glyphs.items() if v)
        return f"slots {s.slots} start {s.at_start} end {s.at_end} glyphs {on}"
    if k == "fields":
        return f"field {s.field} of {s.count} up {s.glyphs.get('up')} down {s.glyphs.get('down')}"
    if k in ("checklist", "checkgrid"):
        return f"focus {s.focus} row {s.row} col {s.field} boxes {s.slots}"
    if k == "look":
        return f"cell {s.field} up {s.glyphs.get('up')} down {s.glyphs.get('down')} marker {s.marker}"
    if k == "slider":
        return f"marker {s.marker} left {s.glyphs.get('left')} right {s.glyphs.get('right')}"
    if k == "wbgrid":
        return f"dot {s.marker} arrows {sorted(g for g, v in s.glyphs.items() if v)}"
    return ""


def report(f, t0, use_ocr):
    s = screen.read(f)
    title = ""
    if use_ocr and f.path:
        lines = ocr.read([f.path])[f.path]
        title = ocr.text_in(lines, (0, 0, 640, 52))
    print(f"{time.monotonic() - t0:7.1f}s  {f.path.name:28s} {s.kind:9s} {describe(s)}"
          + (f"  | {title!r}" if title else ""), flush=True)
    return s


def changed(hdmi, a, b) -> float:
    steady = ~hdmi.noisy(time.monotonic())
    sa, sb = (x.small if x.small is not None else _small(x.image) for x in (a, b))   # OSD frames have none
    return float(((np.abs(sa - sb) > 6.0) & steady).mean())


# drawn over the shooting screen (Bluetooth Rmt Ctrl, Cnct. while Power OFF, Manage Paired Device)
BUSY = ("pairing", "awaiting", "paired device")


def busy_overlay(f) -> bool:
    """A pairing or app-wait message on the shooting screen: a session opened then cuts it short (2026-11-02)."""
    return any(w in ocr.text_in(ocr.read([f.path])[f.path], (0, 0, 640, 120)).lower() for w in BUSY)


def wait_for_shooting(hdmi, why):
    said = False
    while screen.read(hdmi.grab(save=False)).kind != "shooting":
        if not said:
            print(f"waiting for the shooting screen before {why}: please close the menu with MENU", flush=True)
            said = True
        time.sleep(0.5)


def download_when_allowed(link, name: str, tries: int = 6):
    """The camera refuses a settings download while it is busy (CameraSettings_Save_Result_NG: a Bluetooth
    remote's Pairing screen, a menu closing; Api_InvalidCalled: a lens being changed, 2026-11-02): wait and try
    again; None if it never allows it."""
    for _ in range(tries):
        try:
            return link.download(name)
        except LinkError as e:
            # NG: a Pairing screen or a menu closing; Api_InvalidCalled: a lens being changed (2026-11-02)
            if not any(w in str(e) for w in ("NG", "not allow", "InvalidCalled")):
                raise
            print(f"   the camera refused the download ({e}); trying again in 5 s", flush=True)
            time.sleep(5)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--link", action="store_true")
    ap.add_argument("--download", action="store_true")
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--each", action="store_true", help="download and diff on every return to the shooting screen")
    ap.add_argument("--eyes", choices=["hdmi", "osd"], default="hdmi", help="osd: the camera's screen through the SDK")
    ap.add_argument("--closed", action="store_true", help="with --each: a session only for each download")
    a = ap.parse_args()
    a.download = a.download or a.each
    if a.closed and (not a.each or a.eyes == "osd" or a.link):
        sys.exit("--closed needs --each and HDMI eyes (the OSD comes through the session)")
    run = Run("kit2_hdmi_watch")
    hdmi = OsdFeed(run) if a.eyes == "osd" else HdmiSource.from_config(run)
    link = Link(run).open() if (a.link or a.download or a.eyes == "osd") and not a.closed else None
    if a.eyes == "osd":
        hdmi.attach(link)
    hand = open(run.dir / "hand.jsonl", "a", encoding="utf-8", newline="\n") if a.each else None  # noqa: SIM115 (closed in the finally below)

    def fetch(name):
        if not a.closed:
            return download_when_allowed(link, name)
        try:
            with Link(run) as session:
                time.sleep(2)
                got = download_when_allowed(session, name)
        except LinkError as e:                 # Airplane Mode may take the network down (2026-11-02)
            print(f"   could not connect: {e}", flush=True)
            return None
        time.sleep(5)                          # the camera takes a moment to see the session gone
        return got

    try:
        before = None
        if a.download:
            wait_for_shooting(hdmi, "the first settings download")
            before = fetch("before")
            if before is None:           # nothing to diff against: stop before the owner changes anything
                sys.exit("the camera did not allow the first settings download (busy, or the session did not open): "
                         "close any pairing or menu screen on it and run this again")
            print(f"settings saved: {before.name}; wait for 'READY' before pressing MENU", flush=True)
            time.sleep(5)                      # MENU within ~3 s of a download locks the menu
        t0 = time.monotonic()
        last = hdmi.grab("start")
        report(last, t0, a.ocr)
        print("READY: drive the camera; leave every dialog with MENU (never OK)"
              if not a.each else "READY: change one setting; the download after it closes the menu", flush=True)
        seen, prev = [], before
        while not run.stop_requested():
            f = hdmi.peek() if a.eyes == "osd" else hdmi.latest()
            if f is not None and changed(hdmi, f, last) > hdmi.TOL:
                f2, moved = hdmi.settle(last, "seen", expect_change=True, timeout=5)
                if moved:
                    s = report(f2, t0, a.ocr)
                    last = f2
                    came_from = seen[-1]["kind"] if seen else None
                    if a.closed and s.kind == "shooting" and busy_overlay(f2):
                        seen.append({"frame": f2.path.name, "kind": "pairing"})
                        continue
                    if a.each and s.kind != "shooting":
                        seen.append({"frame": f2.path.name, "kind": s.kind})
                    # an option screen closed back to a page (a change made there, or not), or back to the
                    # shooting screen: changes made one after another in one menu visit each get their own
                    # download (the owner stayed in the menu, 2026-11-02)
                    # closed: only on the shooting screen (a session opened in a menu would cut the owner off)
                    if a.each and seen and (s.kind == "shooting" or (not a.closed and
                            s.kind in ("menu", "submenu") and came_from not in (None, "menu", "submenu"))):
                        time.sleep(1.5)
                        now = fetch(f"hand{len(seen):03d}")
                        if now is None:              # keep the frames: the next download covers this change
                            print("   no download this time; carrying on", flush=True)
                            continue
                        changes = camset.diff(camset.read(prev), camset.read(now))
                        hand.write(json.dumps({"before": prev.name, "after": now.name, "frames": seen,
                                               "changes": [{"key": c.key, "before": c.before, "after": c.after}
                                                           for c in changes]}) + "\n")
                        hand.flush()
                        print(f"   {len(changes)} records changed: "
                              + ", ".join(f"{c.key} {c.before!r}->{c.after!r}" for c in changes[:6]), flush=True)
                        prev, seen = now, []
                        time.sleep(4)                  # the menu is locked for ~3 s after a download
                        print("READY", flush=True)
                        last = hdmi.grab("ready")
            time.sleep(0.05)
        print("STOP seen", flush=True)
        if link or a.closed:
            wait_for_shooting(hdmi, "finishing")
        if a.download:
            time.sleep(1)
            after = fetch("after")
            if after is None:
                print("the camera did not allow the last settings download: no final diff", flush=True)
            else:
                changes = camset.diff(camset.read(before), camset.read(after))
                print(f"settings saved: {after.name}; changed records: {len(changes)}", flush=True)
                for c in changes[:40]:
                    print(f"   {c.key}: {c.before!r} -> {c.after!r}", flush=True)
    finally:
        if hand:
            hand.close()
        if link:
            link.close()
        hdmi.close()


if __name__ == "__main__":
    main()
