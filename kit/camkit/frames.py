"""Frames from the camera, in one canonical 640x480 RGB layout, and settle detection.

Sources:
  OsdSource   the SDK's OSD image (already 640x480, about 0.8 s per frame over the LAN)
  HdmiSource  a USB HDMI capture dongle through ffmpeg/AVFoundation, opened BY NAME only
              (device 0 on this Mac is the FaceTime camera; opening it would switch its light on)

Settling: a frame is trusted only once the screen has stopped changing. With HDMI that is measured
directly (frames stop changing for `quiet` seconds). With OSD frames it is inferred from the press's
expected effect: an unchanged frame where a change was expected is re-shot (slow redraws), and an
unexpected change is confirmed by a second frame.
"""
import atexit
import contextlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

from . import config

W, H = 640, 480


@dataclass
class Frame:
    image: np.ndarray            # H x W x 3 uint8 RGB, canonical layout
    t: float                     # time.monotonic() when captured
    path: Path | None = None     # saved evidence
    source: str = ""
    small: np.ndarray | None = None   # 80x60 thumbnail, kept by sources that compare every frame

    def save(self, path: Path, withheld: bool = False) -> Path:
        """The frame written to `path` as evidence; `withheld` (the eyes' withheld: a row whose values an owner decision
        withholds is open, camkit.live.LiveCamera) writes a black picture of the same size instead, so no pixel of that
        screen ever reaches the disk, while the frame in memory keeps its picture for the screen's kind."""
        Image.fromarray(np.zeros_like(self.image) if withheld else self.image).save(path)
        self.path = path
        return path


def keep(f: Frame, path: Path, withheld: bool = False) -> Path:
    """`f` saved as evidence at `path`: black where `withheld` (Frame.save), as it is otherwise."""
    return f.save(path, True) if withheld else f.save(path)


def load(path: Path, source="file") -> Frame:
    """OSD images are RGBA with live view left transparent: composite onto black, which is what
    HDMI shows with the lens cap on, so both sources look alike to the screen reader."""
    with Image.open(path) as opened:
        img = opened.convert("RGBA") if opened.mode in ("RGBA", "LA", "P") else opened.convert("RGB")
    if img.mode == "RGBA":
        img = Image.alpha_composite(Image.new("RGBA", img.size, (0, 0, 0, 255)), img).convert("RGB")
    if img.size != (W, H):
        img = img.resize((W, H), Image.LANCZOS)
    return Frame(np.asarray(img), time.monotonic(), Path(path), source)


# ------------------------------------------------------------------ comparing frames

def _small(img: np.ndarray) -> np.ndarray:
    """80x60 grey thumbnail: tolerant of compression noise, still sees one row moving."""
    g = img.astype(np.float32).mean(axis=2)
    return g.reshape(60, H // 60, 80, W // 80).mean(axis=(1, 3))


def changed_fraction(a: np.ndarray, b: np.ndarray, level=6.0) -> float:
    """Share of 8x8-pixel blocks whose mean brightness moved by more than `level`."""
    return float((np.abs(_small(a) - _small(b)) > level).mean())


def same(a: Frame | None, b: Frame | None, tol=0.0) -> bool:
    if a is None or b is None:
        return False
    return changed_fraction(a.image, b.image) <= tol


# ------------------------------------------------------------------ sources

class OsdSource:
    """The SDK keeps the camera's latest OSD image and refreshes it by itself: after the first grab
    of a session (~0.8 s) a grab costs 1-2 ms, so polling every 40 ms works like a slow live feed.
    Measured 2026-10-27: after MENU the first changed frame (0.36 s) still had its rows half drawn;
    the shooting screen flickers ~0.5% (exposure readout), hence TOL.
    Measured 2026-11-06 (LAN): the image renews every 0.25-0.37 s, and a press shows 0.33-0.65 s after it
    was sent. Between renewals every poll returns the same picture, so "unchanged for 0.2 s" is one picture
    seen five times, not a screen at rest: a menu sliding in passed for settled, the group column read as
    focused, and the Right meant for it opened the row the cursor was really on. QUIET is the floor: two
    renewals with the same picture. LATE is how long a press that shows nothing is given before it counts
    as ignored: the image froze for 3.25 s and for 6.6 s on 2026-11-06 while the camera went on answering
    presses (an OK, then an Up and two MENUs, all shown only when the picture caught up), so a press is given
    6 s, which costs that long only when a press really did nothing."""
    name = "osd"
    TOL = 0.01
    QUIET = 0.75
    LATE = 6.0
    # set by camkit.live.LiveCamera while a row whose values an owner decision withholds is open: every frame saved is
    # black (Frame.save), and the camera's own picture is polled into a folder of these eyes' own outside the run's
    # folder (private_dir: tempfile.mkdtemp, mode 0700 and a name no other user can guess), the picture and camlink's
    # .part beside it removed as soon as it is read (peek), the folder at close() and when the process ends: camlink
    # writes that picture, so it is on the disk for that moment, where only this user can read it
    withheld = False
    _private = None

    def __init__(self, link, run):
        self.link, self.run = link, run
        self.live = run.dir / "_live.png"      # polling target; only settled frames become evidence

    def private_dir(self) -> Path:
        """The folder the withheld polls go to: made once (tempfile.mkdtemp, mode 0700) and kept until close()."""
        d = getattr(self, "_private", None)
        if d is None or not Path(d).is_dir():
            d = self._private = Path(tempfile.mkdtemp(prefix="camkit_osd_"))
            atexit.register(shutil.rmtree, d, True)         # an exception that skips close() still takes it away
        return d

    def close_private(self) -> None:
        """The withheld polls' folder removed, whatever is left in it (a camlink killed mid-write leaves its .part)."""
        d, self._private = getattr(self, "_private", None), None
        if d is not None:
            shutil.rmtree(d, ignore_errors=True)

    def close(self):
        self.close_private()
        self.forget_live()

    def forget_live(self) -> None:
        """The polling target at the top of the run's folder (live, and camlink's .part beside it) taken away: it is a
        real frame of whatever was polled last, never evidence (2026-11-14: an owner run's, values logged, sat beside
        shots/), so no run leaves it behind."""
        live = getattr(self, "live", None)
        if live is None:
            return
        for left in (Path(live), Path(live).with_name(Path(live).name + ".part")):
            with contextlib.suppress(OSError):
                left.unlink()

    def peek(self) -> Frame:
        if not getattr(self, "withheld", False):
            self.link.osd(self.live)
            f = load(self.live, "osd")
            f.path = None
            return f
        target = self.private_dir() / "withheld.png"
        try:
            self.link.osd(target)
            f = load(target, "osd")
        finally:
            for left in (target, target.with_name(target.name + ".part")):
                with contextlib.suppress(OSError):
                    left.unlink()
        f.path = None
        return f

    def grab(self, tag="f") -> Frame:
        f = self.peek()
        keep(f, self.run.shot_path(tag), getattr(self, "withheld", False))
        return f

    def settle(self, before: Frame | None, tag="f", expect_change: bool | None = None,
               timeout=3.0, quiet=0.2, poll=0.04) -> tuple[Frame, bool]:
        """Poll until the screen has not changed for `quiet` s; (frame, changed since `before`).

        When a change is expected but nothing has moved yet, keep waiting for up to `timeout`
        (slow redraws); a no-op is declared only after a longer quiet window."""
        start = time.monotonic()
        quiet = max(quiet, self.QUIET)
        timeout = max(timeout, quiet + self.LATE)
        last, stable_since, moved = None, None, before is None
        while time.monotonic() - start < timeout:
            f = self.peek()
            if not moved and not same(f, before, self.TOL):
                moved = True
            if last is not None and same(f, last, self.TOL):
                stable_since = stable_since or last.t
                need = quiet if moved else (self.LATE if expect_change else quiet)
                if f.t - stable_since >= need:
                    break
            else:
                stable_since = None
            last = f
            time.sleep(poll)
        f = last or self.peek()
        keep(f, self.run.shot_path(tag), getattr(self, "withheld", False))
        return f, moved


class OsdFeed(OsdSource):
    """The camera's own screen through the SDK, in place of an HDMI capture dongle: the same calls as
    HdmiSource (grab, settle, timing, noisy, close). Scripts build their eyes before a session opens,
    so this one is attached to the link once it does (`attach`). For bodies without HDMI capture
    (private/config.json "eyes": "osd"); a run that sees through it must also have scanned the menu
    through it, since OSD frames do not match a scan made over HDMI."""
    name = "osd"

    def __init__(self, run):
        self.run, self.link, self.timing = run, None, {}
        self.live = run.dir / "_live.png"

    def attach(self, link):
        self.link = link

    def peek(self) -> Frame:
        if self.link is None:
            raise RuntimeError("the OSD eyes need an open camera link (attach it first)")
        return super().peek()

    def grab(self, tag="f", save=True) -> Frame:
        return super().grab(tag) if save else self.peek()

    def settle(self, before, tag="f", expect_change=None, timeout=3.0, quiet=0.2, sent_at=None, **_):
        return super().settle(before, tag, expect_change, timeout=timeout, quiet=quiet)

    def noisy(self, until: float, level=6.0) -> np.ndarray:
        return np.zeros((60, 80), bool)        # no blinking readouts to learn: frames come on request

    def close(self):
        self.close_private()                    # the withheld polls' folder, if a withheld row made one
        self.forget_live()                      # and the polling target at the top of the run's folder


def eyes_default() -> str:
    """private/config.json "eyes": "hdmi" when a config leaves it out (the capture dongle it was calibrated
    for), "osd" with no config at all (the baseline: no dongle needed, docs/QUICKSTART.md)."""
    c = config(required=False)
    return c.get("eyes", "hdmi" if c else "osd")


def eyes_from_config(run):
    """The kit's eyes as CAMSET_EYES or private/config.json "eyes" says: "hdmi" (the capture dongle) or "osd"
    (the camera's own screen through the SDK; attach the link once a session opens); see eyes_default."""
    if (os.environ.get("CAMSET_EYES") or eyes_default()) == "osd":    # CAMSET_EYES overrides
        return OsdFeed(run)
    return HdmiSource.from_config(run)


def avfoundation_devices() -> list[str]:
    out = subprocess.run(["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
                         capture_output=True, text=True).stderr
    video = out.split("video devices:")[1].split("audio devices:")[0] if "video devices:" in out else ""
    return re.findall(r"\[\d+\] (.+)", video)


def dshow_devices() -> list[str]:
    """Windows: DirectShow video devices, from ffmpeg's listing ("NAME" (video), or the older
    section form)."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    found = re.findall(r'"([^"]+)" \(video\)', out)
    if not found and "DirectShow video devices" in out:
        video = out.split("DirectShow video devices")[1].split("DirectShow audio devices")[0]
        found = [n for n in re.findall(r'"([^"]+)"', video) if not n.startswith("@device")]
    return found


def v4l2_devices() -> dict[str, str]:
    """Linux: {name: /dev/videoN} for each device's capture node (index 0; the others carry metadata)."""
    out = {}
    for d in sorted(Path("/sys/class/video4linux").glob("video*"), key=lambda p: int(p.name[5:] or 0)):
        try:
            if (d / "index").read_text(encoding="utf-8").strip() != "0":
                continue
            out.setdefault((d / "name").read_text(encoding="utf-8").strip(), f"/dev/{d.name}")
        except OSError:
            continue
    return out


def capture_devices() -> list[str]:
    if sys.platform == "darwin":
        return avfoundation_devices()
    if os.name == "nt":
        return dshow_devices()
    return list(v4l2_devices())


def capture_input(device: str, size, fps) -> list[str]:
    """ffmpeg's input arguments for the named dongle on this OS: avfoundation (macOS), dshow (Windows)
    or v4l2 (Linux). A Linux device may also be given as its /dev/videoN path."""
    w, h = size
    if sys.platform == "darwin":
        return ["-f", "avfoundation", "-framerate", str(fps), "-video_size", f"{w}x{h}", "-i", f"{device}:none"]
    if os.name == "nt":
        return ["-f", "dshow", "-rtbufsize", "64M", "-framerate", str(fps), "-video_size", f"{w}x{h}",
                "-i", f"video={device}"]
    node = device if device.startswith("/dev/") else next(
        (n for name, n in v4l2_devices().items() if device.lower() in name.lower()), device)
    return ["-f", "v4l2", "-framerate", str(fps), "-video_size", f"{w}x{h}", "-i", node]


def scaled_crop(crop, size, capture) -> tuple:
    """The calibrated crop (x, y, width, height, measured on frames of `size`) on frames of `capture`, each number scaled
    by capture/size and rounded: 1080p's (150, 0, 1620, 1080) is (300, 0, 3240, 2160) at 2160p. A capture of another
    shape than the calibration's is refused (ValueError, in plain words): the crop cannot be scaled onto it."""
    (cw, ch), (sw, sh) = (int(v) for v in capture), (int(v) for v in size)
    if abs(cw * sh - ch * sw) > max(cw, sw):          # a pixel's rounding aside, the same shape
        raise ValueError(f"the dongle's capture size {cw}x{ch} is not the shape of {sw}x{sh}, the size the crop was "
                         "measured on, so the crop cannot be scaled onto it: ask the dongle for a mode of that shape "
                         "(\"capture\" in private/config.json's \"hdmi\"), or measure the crop again on the capture size")
    fx, fy = cw / sw, ch / sh
    x, y, w, h = crop
    return round(x * fx), round(y * fy), round(w * fx), round(h * fy)


def hdmi_settings(c: dict) -> dict:
    """The dongle's settings from private/config.json's "hdmi" (`c`): "size", "fps" and "crop" are the calibration's
    (the frames the crop was measured on); "capture" ({"size": [W, H], "fps": F}, optional) is the mode asked of the
    dongle, its fps the calibration's when not given; absent, the dongle is asked for the calibration's size and fps,
    as before. A "capture" with no size of two positive whole numbers, or no positive fps, is refused in plain words."""
    out = {"device": c["device"], "size": tuple(c["size"]), "fps": c["fps"],
           "crop": tuple(c["crop"]) if c.get("crop") else None, "capture": None}
    cap = c.get("capture")
    if cap is None:
        return out
    size, fps = (cap.get("size"), cap.get("fps", c["fps"])) if isinstance(cap, dict) else (None, None)
    good = (isinstance(size, list) and len(size) == 2 and all(isinstance(v, int) and v > 0 for v in size)
            and isinstance(fps, (int, float)) and not isinstance(fps, bool) and fps > 0)
    if not good:
        raise ValueError(f"private/config.json's \"hdmi\" \"capture\" is {cap!r}: it takes {{\"size\": [width, height], "
                         "\"fps\": rate}, the mode the dongle offers, such as {\"size\": [3840, 2160], \"fps\": 29.97}")
    out["capture"] = (tuple(size), fps)
    return out


def hdmi_command(device: str, size, fps, crop, capture=None) -> tuple:
    """(ffmpeg's command line, the size of the frames it writes) for the dongle: asked for `capture` ((size, fps), the
    mode it offers; the calibration's `size` and `fps` when None), its picture cropped by the calibration's `crop`
    scaled onto the capture (scaled_crop) and scaled to the canonical 640x480 in that one step, so the picture is
    resampled once; with no crop, the capture's frames whole."""
    cap_size, cap_fps = capture if capture else (tuple(size), fps)
    vf = []
    if crop:
        x, y, w, h = scaled_crop(crop, size, cap_size) if tuple(cap_size) != tuple(size) else tuple(crop)
        vf = ["-vf", f"crop={w}:{h}:{x}:{y},scale={W}:{H}:flags=lanczos"]
    # passthrough + no buffering: by default ffmpeg pads rawvideo output to a constant rate with
    # duplicate frames (2026-10-28: ~400 frames/s arrived and the picture lagged the camera)
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-fflags", "nobuffer", "-flags", "low_delay",
           "-probesize", "32", "-analyzeduration", "0",
           *capture_input(device, cap_size, cap_fps), *vf, "-fps_mode", "passthrough", "-f", "rawvideo", "-pix_fmt",
           "rgb24", "-"]
    return cmd, ((W, H) if crop else tuple(cap_size))


MODE = re.compile(r"(\d+)x(\d+)@\[([\d.]+)\s+([\d.]+)\]\s*fps")      # one mode ffmpeg lists a dongle offering


def feed_error(lines, size, fps) -> str:
    """Why the dongle sent no frames, in plain words, from ffmpeg's error lines (`lines`), the mode asked being `size`
    at `fps`: where ffmpeg says that mode is not supported and lists the modes it is, what was asked, the modes offered
    as ffmpeg listed them, and what to do; else a plain sentence that sends to the run's log, where ffmpeg's own words
    are (HdmiSource logs them). ffmpeg's lines themselves are never in it."""
    text = " ".join(str(x) for x in lines or ())
    w, h = size
    asked = f"{w}x{h} at {fps:g} fps"
    if re.search(r"not supported by the device", text):
        modes = []
        for m in MODE.finditer(text):
            mode = f"{m.group(1)}x{m.group(2)} at {float(m.group(3)):g} fps"
            if mode not in modes:
                modes.append(mode)
        first = MODE.search(text)
        example = (f"{{\"size\": [{first.group(1)}, {first.group(2)}], \"fps\": {float(first.group(3)):g}}}" if first
                   else "{\"size\": [width, height], \"fps\": rate}")
        offers = f"it offers {', '.join(modes)} (as ffmpeg listed them)" if modes else "ffmpeg listed no mode it offers"
        return (f"the capture dongle does not offer {asked}, the mode the kit asked of it; {offers}. Put that mode under "
                f"\"capture\" in private/config.json's \"hdmi\" ({example}): the kit then scales the crop to it. Or set "
                "the camera's HDMI Resolution back to the size the crop was measured on (a camera reset puts it on "
                "Auto)")
    return (f"the capture dongle sent no frames: ffmpeg could not read it at {asked} (its own words are in the run's "
            "log). Check the cable, that the camera's HDMI output is on, and the mode asked (private/config.json's "
            "\"hdmi\": \"capture\", else its size and fps)")


class HdmiSource:
    """Continuous capture from a named HDMI dongle; grab() returns the newest frame.

    With a calibrated crop, ffmpeg crops and scales to the canonical layout itself, so only 640x480
    frames reach Python (a tenth of the data at 59.94 fps). A dongle that offers another size than the crop was
    measured on is asked for its own ("capture", hdmi_settings) and the crop scaled onto it in that one step
    (hdmi_command): the owner's Cam Link 4K offered 3840x2160 at 29.97 fps alone after a camera reset (2026-11-18)."""
    name = "hdmi"
    withheld = False        # as OsdSource's: while set, every frame saved is black (Frame.save)
    # share of 8x8 blocks: ~5 blocks. Once self-changing blocks are masked the uncompressed feed has a
    # zero noise floor (2026-10-28), and one digit stepping in a number field moves ~6-12 blocks.
    TOL = 0.001
    HISTORY = 2.5        # s of thumbnails kept to learn which blocks change by themselves
    NOISY_WINDOW = 2.0   # before a press: blocks that blinked in this window are ignored by settle()
    REFUSE = re.compile(r"facetime|iphone|continuity|desk view|integrated|webcam", re.I)   # never a built-in camera

    def __init__(self, run, device: str, size=(1920, 1080), fps=30, crop: tuple | None = None, capture=None):
        """size, fps, crop: the calibration's (the frames the crop was measured on); capture: (size, fps), the mode
        asked of the dongle (hdmi_settings' "capture"), the calibration's own when None. The frames the dongle sends
        are the capture's: size and fps here are its (calibrated_size keeps the calibration's)."""
        if self.REFUSE.search(device):
            raise ValueError(f"refusing to open {device!r}: not a capture dongle")
        found = capture_devices()
        linux = sys.platform.startswith("linux")      # v4l2 names carry extras ("Cam Link 4K: Cam Link 4K")
        if not (device in found or device.startswith("/dev/") or (linux and any(device.lower() in d.lower() for d in found))):
            raise ValueError(f"no capture device named {device!r}; found {found}")
        self.run, self.crop, self.calibrated_size = run, crop, tuple(size)
        self.cmd, self.out = hdmi_command(device, size, fps, crop, capture)
        self.capture_size, self.fps = (tuple(capture[0]), capture[1]) if capture else (tuple(size), fps)
        self.size = self.capture_size       # what the dongle sends, for anything that times or sizes by the source
        self._lock = threading.Lock()
        self._latest: Frame | None = None
        self._hist: deque = deque()          # (t, thumbnail)
        self._restarted = 0.0
        self.errors: deque = deque(maxlen=20)          # ffmpeg's last error lines
        self._start()

    def _start(self):
        self.proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self._running = True
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
        threading.Thread(target=self._drain, args=(self.proc,), daemon=True).start()

    def _drain(self, proc):
        """ffmpeg's error lines as they come, the last few kept for the error a stopped feed raises. A pipe nobody
        reads fills up (64 KB) and blocks ffmpeg in its next write: a dongle repeating an error stopped the feed."""
        with proc.stderr:
            for raw in proc.stderr:
                self.errors.append(raw.decode("utf-8", errors="replace").strip())

    @staticmethod
    def _stop(proc):
        """ffmpeg stopped, and waited for, so no process is left behind. Killed, not asked: it has nothing to finish
        here, and one blocked writing a frame nobody reads any more does not act on SIGTERM (its write is restarted)."""
        proc.kill()
        with contextlib.suppress(subprocess.TimeoutExpired):
            proc.wait(3)

    @classmethod
    def from_config(cls, run):
        """The dongle as calibrated in private/config.json "hdmi", asked for its "capture" mode where one is given
        (hdmi_settings)."""
        return cls(run, **hdmi_settings(config()["hdmi"]))

    def no_frames(self, why: str) -> str:
        """The error a feed that sends no frames raises: feed_error's plain words from ffmpeg's last lines (a refused
        mode names the modes the dongle offers), those lines themselves in the run's log alone ("hdmi_feed_error")."""
        lines = list(getattr(self, "errors", ()) or ())
        if lines:
            with contextlib.suppress(Exception):            # a log that cannot be written changes no error
                self.run.log("hdmi_feed_error", why=why, ffmpeg=lines)
            return feed_error(lines, getattr(self, "capture_size", None) or getattr(self, "size", (0, 0)),
                              getattr(self, "fps", 0))
        return why

    def _read(self, proc):
        w, h = self.out
        n = w * h * 3
        with proc.stdout:              # closed here when this ffmpeg's feed ends, not left to the garbage collector
            while self._running and proc is self.proc:
                buf = proc.stdout.read(n)
                if len(buf) < n:
                    break
                img = np.frombuffer(buf, np.uint8).reshape(h, w, 3)
                img = img if self.crop else canonical(img)
                f = Frame(img, time.monotonic(), None, "hdmi", _small(img))
                with self._lock:
                    self._latest = f
                    self._hist.append((f.t, f.small))
                    while f.t - self._hist[0][0] > self.HISTORY:
                        self._hist.popleft()

    def noisy(self, until: float, level=6.0) -> np.ndarray:
        """Blocks that blinked in the NOISY_WINDOW s before `until`: changed by themselves at least
        twice, between frames where little else changed. While a remote session is open the exposure
        readouts ("±0.0", "ISO AUTO") toggle every ~0.63 s, ~1% of the blocks (2026-10-28; not with
        the link closed). Frame pairs where over 5% of the screen changed (a dialog opening or
        closing) are left out: counting menu -> dialog -> menu as back-and-forth masked ~4,400 of
        4,800 blocks and hid the next press (first live crawl, 2026-10-28)."""
        with self._lock:
            smalls = [sm for t, sm in self._hist if until - self.NOISY_WINDOW <= t < until]
        if len(smalls) < 3:
            return np.zeros((60, 80), bool)
        d = np.abs(np.diff(np.stack(smalls), axis=0)) > level
        small = d[d.mean(axis=(1, 2)) < 0.05]
        return small.sum(axis=0) >= 2 if len(small) else np.zeros((60, 80), bool)

    STALE = 2.0          # s without a new frame: the feed has stopped

    def latest(self) -> Frame | None:
        """The newest frame. The feed runs at the input's rate even on a still picture, so a frame older
        than STALE means it stopped (Movie mode can change the HDMI frame rate under ffmpeg, 2026-10-30):
        that is never an old picture to act on. ffmpeg is restarted once (the signal may be back to the
        calibrated format by now); if no fresh frame comes, it is an error."""
        with self._lock:
            f = self._latest
        if f is not None and time.monotonic() - f.t > self.STALE:
            if time.monotonic() - self._restarted > 30:
                self._restarted = time.monotonic()
                self._running = False
                self._stop(self.proc)
                with self._lock:
                    self._latest = None
                self._start()
                end = time.monotonic() + 6
                while time.monotonic() < end:
                    with self._lock:
                        f = self._latest
                    if f is not None:
                        return f
                    time.sleep(0.05)
            raise RuntimeError(self.no_frames("the capture dongle stopped sending frames"))
        return f

    def grab(self, tag="f", save=True) -> Frame:
        end = time.monotonic() + 5
        while (f := self.latest()) is None:
            if time.monotonic() > end:
                raise RuntimeError(self.no_frames("no frames from the capture dongle"))
            time.sleep(0.01)
        f = Frame(f.image, f.t, None, "hdmi", f.small)
        if save:
            keep(f, self.run.shot_path(tag), getattr(self, "withheld", False))
        return f

    def settle(self, before: Frame | None, tag="f", expect_change: bool | None = None,
               timeout=3.0, quiet=0.15, sent_at: float | None = None) -> tuple[Frame, bool]:
        """Wait for the screen to stop changing; (frame, changed since `before`).

        Same rule as OsdSource.settle: when a change is expected but nothing has moved yet, keep
        waiting (MENU takes ~0.4 s to start drawing; 2026-10-28 a 0.35 s window gave up too early).
        Blocks that were already changing before `start` (blinking readouts) are ignored, so a blink
        is neither taken for the press's effect nor allowed to keep the screen from settling.
        self.timing holds when the screen first moved and when it went quiet, from `start`."""
        start = sent_at or time.monotonic()
        steady = ~self.noisy(start)

        def share(x, y):
            return float(((np.abs(x - y) > 6.0) & steady).mean())

        b = _small(before.image) if before is not None else None
        last, stable_since, moved, moved_at = None, None, before is None, None
        while time.monotonic() - start < timeout:
            f = self.latest()
            if f is None or f.t < start or (last is not None and f.t == last.t):
                time.sleep(0.005)
                continue
            if not moved and share(f.small, b) > self.TOL:
                moved, moved_at = True, f.t
            if last is not None and share(f.small, last.small) <= self.TOL:
                stable_since = stable_since or last.t
                need = quiet if moved else (1.0 if expect_change else 0.5)
                if f.t - stable_since >= need:
                    break
            else:
                stable_since = None
            last = f
        self.timing = {"moved": moved_at and round(moved_at - start, 3),
                       "settled": stable_since and round(stable_since - start, 3),
                       "ignored_blocks": int((~steady).sum())}
        f = self.grab(tag)
        return f, moved

    def settle_box(self, box, prior=None, quiet: float = 0.15, timeout: float = 3.5) -> tuple:
        """Wait until the picture inside `box` (x0, y0, x1, y1 of the 640x480 frame) has stopped changing for `quiet`
        s and, with `prior` (an image: the frame a press was made on), differs from prior's there: (the latest frame,
        not saved; whether it differs from prior's). The blocks that changed by themselves before the wait began are
        ignored there, as settle ignores them. At `timeout` the latest frame, as it is."""
        start = time.monotonic()
        x0, y0, x1, y1 = box
        cells = (slice(y0 // 8, -(-y1 // 8)), slice(x0 // 8, -(-x1 // 8)))
        steady = ~self.noisy(start)[cells]

        def moved(a, b):
            return bool(((np.abs(a[cells] - b[cells]) > 6.0) & steady).any())
        before = _small(prior) if prior is not None else None
        last, still_since, changed = None, None, before is None
        while time.monotonic() - start < timeout:
            f = self.latest()
            if f is None or (last is not None and f.t == last.t):
                time.sleep(0.005)
                continue
            changed = changed or moved(f.small, before)
            if last is not None and not moved(f.small, last.small):
                still_since = still_since or last.t
                if changed and f.t - still_since >= quiet:
                    last = f
                    break
            else:
                still_since = None
            last = f
        f = last if last is not None else self.grab(save=False)
        return Frame(f.image, f.t, None, "hdmi", f.small), changed

    def attach(self, link):
        """Nothing to do: HDMI needs no camera link (OsdFeed does)."""

    def close(self):
        self._running = False
        self._stop(self.proc)


def canonical(img: np.ndarray, crop: tuple | None = None) -> np.ndarray:
    """Crop to the camera's UI area and scale to 640x480.

    Default crop for a 16:9 frame is the centred 4:3 region. Measured 2026-10-28 on the a1 II at 1080p:
    the UI is a 3:2 area at x 150-1770 that scales exactly onto the OSD layout (private/config.json "hdmi"). A frame
    of another size takes the crop scaled onto it (scaled_crop), as HdmiSource's capture does.
    """
    h, w = img.shape[:2]
    if crop is None:
        cw = round(h * 4 / 3)
        crop = ((w - cw) // 2, 0, cw, h) if cw < w else (0, 0, w, h)
    x, y, cw, ch = crop
    sub = img[y:y + ch, x:x + cw]
    if sub.shape[:2] == (H, W):
        return np.ascontiguousarray(sub)
    return np.asarray(Image.fromarray(sub).resize((W, H), Image.LANCZOS))
