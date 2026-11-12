"""Step-1 check of the new kit on the camera: link, frames, pixel reader, OCR.

    .venv/bin/python kit/tools/selftest.py [--no-press] [--eyes osd|hdmi]     # default: the configured eyes

Connects over the LAN, reads the firmware and the property count, grabs a frame and classifies it.
With --eyes hdmi it grabs the start screen from both the OSD and the HDMI dongle (private/config.json "hdmi")
and compares them, then watches the presses through HDMI.
Unless --no-press: presses MENU (expects a menu page), reads its breadcrumb, presses MENU again
(expects the shooting screen). MENU is the only button pressed. Evidence goes to runs/<model>_fw<fw>/kit2_selftest.
"""
import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ocr, screen  # noqa: E402
from camkit.frames import HdmiSource, OsdSource, changed_fraction, eyes_default  # noqa: E402
from camkit.link import Link  # noqa: E402
from camkit.runs import Run  # noqa: E402


def show(label, frame, s, t0, eyes=None):
    timing = getattr(eyes, "timing", None)
    extra = (f"  (first change {timing['moved']} s, settled {timing['settled']} s, "
             f"{timing['ignored_blocks']} blinking blocks ignored)") if timing else ""
    print(f"{label:<14} {s.kind:<9} {frame.path.name}  {time.monotonic() - t0:5.2f} s{extra}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-press", action="store_true")
    ap.add_argument("--eyes", choices=("osd", "hdmi"), default=os.environ.get("CAMSET_EYES") or eyes_default())
    a = ap.parse_args()
    run = Run("kit2_selftest")
    hdmi = HdmiSource.from_config(run) if a.eyes == "hdmi" else None
    try:
        with Link(run) as link:
            check(link, run, hdmi, a.no_press)
    finally:
        if hdmi:
            hdmi.close()


def check(link, run, hdmi, no_press):
    fw = link.get("SoftwareVersion").get("text")
    props = link.props()
    print(f"camera {link.model}  firmware {fw}  {len(props)} properties")
    osd = OsdSource(link, run)
    eyes = hdmi or osd

    t0 = time.monotonic()
    f0 = osd.grab("start_osd")
    s0 = screen.read(f0)
    show("start (OSD)", f0, s0, t0)
    if hdmi:
        t0 = time.monotonic()
        f0 = hdmi.grab("start_hdmi")
        h0 = screen.read(f0)
        show("start (HDMI)", f0, h0, t0)
        same_kind = (h0.kind, h0.row) == (s0.kind, s0.row)
        print(f"               HDMI vs OSD: {'same' if same_kind else 'DIFFERENT'} screen "
              f"({100 * changed_fraction(f0.image, osd.peek().image):.1f}% of blocks differ)")
        s0 = h0
    if no_press:
        return
    if s0.kind != "shooting":
        print("not on the shooting screen; not pressing anything")
        return

    t0 = time.monotonic()
    link.press("menu")
    f1, changed = eyes.settle(f0, "menu_open", expect_change=True)
    s1 = screen.read(f1)
    show("MENU", f1, s1, t0, eyes)
    if s1.kind == "menu":
        lines = ocr.read([f1.path])[f1.path]
        print(f"               breadcrumb: {ocr.text_in(lines, (0, 0, 540, 42))!r}  "
              f"page: {ocr.text_in(lines, (540, 0, 640, 42))!r}  row slot: {s1.row}")

    t0 = time.monotonic()
    if s1.kind == "menu":
        link.press("menu")
        f2, _ = eyes.settle(f1, "menu_close", expect_change=True)
        s2 = screen.read(f2)
        show("MENU again", f2, s2, t0, eyes)
        print("OK" if s2.kind == "shooting" else "UNEXPECTED: not back on the shooting screen")
    else:
        print(f"UNEXPECTED after MENU: {s1.kind}; leaving the camera as it is")


if __name__ == "__main__":
    main()
