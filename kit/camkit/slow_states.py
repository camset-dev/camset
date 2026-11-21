"""The camera states in which the camera has been seen to act on one button press twice, where the kit presses
nothing (2026-11-21): an Enter counted twice could choose what the kit never meant to.

Each known state is named the way the kit names a camera's settings, never by bare record numbers: the shooting mode
by the camera file's `live_mode` (its modes' names), the setting by its name in the camera's definition and the value
by its label there. On the a1 II: the S&Q family (live_mode's "S&Q", global:0x13bf = 2) with S&Q Frame Rate at "1fps"
(the definition's "S&Q Frame Rate", global:0x0248 = 15). There the camera moved two menu tabs for one press sent, twice
in five presses (kit2_greyrow 04496 and 04497: Focus to Network, Network to My Menu), and two row walks at that rate
ended one row off. At the eight other rates the kit walked (240, 120, 60, 30, 15, 8, 4 and 2 fps, lead_sq_framerate and
lead_sq_framerate2) no tab moved twice (370 tab moves over those runs, the frame-rate chains and kit2_greyrow's looks,
the two above aside) and every look reached its row; 100, 50, 25, 12, 6 and 3 fps
were never walked, nor Time-lapse at an interval but the working file's, so nothing is known of them either way.
Another body's definition names its own setting and values: where it
has a setting of that name with a value of that label, and a live mode of that name, the same check holds for it;
where any of the three is missing, the check is silent (nothing refused), since nothing is known of that body.

Where it is judged: runner.session_start, the start every prover, walker and drive passes, on its start download,
before any press of the run's own (the start's way to the shooting screen aside: MENU, and only where a menu is
open); kit/provers/filter_run.py and kit/tools/take_picture.py, which make their own start, the same way;
kit/provers/mode_switch.py --to, before its switch, where the start file would land the camera in such a state (the
mode it switches to, the frame rate the file holds), and --set, which never sets one; kit/drive.py, whose Enter never
chooses one on its --path's row; and camkit.link.Link.download, every download a run makes: one in such a state (a
run's own choice, prove_run's or a table walk's, put the camera there) leaves the link pressing nothing but MENU until
the run's restore (after_download). The words to the owner name no frame (the frames are above). The ways out press nothing:
a settings file uploaded (kit/tools/upload_check.py, a restore, a chain's end file) or the owner's hand."""
import re

from . import camset

# (the live mode's name, the setting's name in the definition, the value's label, what was seen)
KNOWN = (
    ("S&Q", "S&Q Frame Rate", "1fps", "it moved two menu tabs for a single press"),     # kit2_greyrow 04496, 04497
)
KEY = re.compile(r"(global|set(\d+)):0x([0-9a-f]{4})")


def _where(key) -> tuple | None:
    m = KEY.fullmatch(str(key or ""))
    return (0 if m[1] == "global" else int(m[2]), int(m[3], 16)) if m else None


def states(doc: dict) -> list:
    """The known states this camera's definition names whole: [{"mode", "live", "live_code", "setting", "where",
    "code", "label", "row", "seen"}], each with the live mode's record and code, the setting's global record, the
    value's code and the setting's menu row; a state the definition does not name whole is left out (silent)."""
    camera = (doc or {}).get("camera") or {}
    lm = camera.get("live_mode") or {}
    live = _where(lm.get("key"))
    out = []
    for mode, name, label, seen in KNOWN:
        code = next((int(c) for c, n in (lm.get("modes") or {}).items() if n == mode and str(c).isdigit()), None)
        if live is None or code is None:
            continue
        for s in (doc or {}).get("settings") or []:
            where = _where(s.get("key"))
            if s.get("name") != name or where is None or where[0] != 0:
                continue
            value = next((v for v, lab in s.get("values") or [] if lab == label), None)
            if value is None:
                continue
            out.append({"mode": mode, "live": live, "live_code": code, "setting": name, "where": where, "code": value,
                        "label": label, "row": " > ".join(map(str, s.get("row") or [name])), "seen": seen})
    return out


def held(doc: dict, read, mode: str | None = None) -> dict | None:
    """The known state a settings file holds, by `read(section, record_id)` -> its value or None, else None. `mode`:
    the shooting mode the camera will be in (a switch's target); None, the file's own live mode."""
    for st in states(doc):
        try:
            live = read(*st["live"])
            value = read(*st["where"])
        except Exception:               # a file that cannot be read says nothing: silent
            return None
        in_mode = (mode == st["mode"]) if mode is not None else (live == st["live_code"])
        if in_mode and value == st["code"]:
            return st
    return None


def file_reader(path):
    """read(section, record_id) for a settings file, or None where it cannot be read (a test's stand-in, a file gone)."""
    try:
        cs = camset.read(path)
    except Exception:
        return None

    def read(section, rid):
        r = cs.get(section, rid)
        return r.value() if r is not None else None
    return read


def refusal(doc: dict, path, mode: str | None = None, doing: str = "") -> str:
    """Why the run presses nothing with the camera in the settings file `path` (a known state, held: the lay owner's
    words: what the kit saw, why it will not press, what to do), or "" (none held, or nothing known: silent)."""
    read = file_reader(path)
    st = held(doc, read, mode) if read is not None else None
    if st is None:
        return ""
    now = "would put the camera in" if mode is not None else "found the camera in"
    return (f"{doing or 'This run'} {now} {st['mode']} mode with {st['setting']} at {st['label']}. In that state this "
            f"camera has been seen to act on one button press twice ({st['seen']}), so the kit could choose something it "
            "did not mean to. Nothing more was pressed. To go on, set "
            f"{st['setting']} to any other rate on the camera by hand (MENU > {st['row']}), or load a settings file "
            "that holds another rate (kit/tools/upload_check.py FILE), then run this again.")


def after_download(doc: dict, path) -> str:
    """Why nothing more but MENU is pressed on the link that downloaded `path`, a settings file in a known state (a
    run's own choice put the camera there: camkit.link.Link.download judges every download), or "" (none held, nothing
    known, or the file cannot be read: silent)."""
    read = file_reader(path) if states(doc) else None
    st = held(doc, read) if read is not None else None
    if st is None:
        return ""
    return (f"The settings just downloaded show {st['mode']} mode with {st['setting']} at {st['label']}. In that state "
            f"this camera has been seen to act on one button press twice ({st['seen']}), so nothing more is pressed but "
            "MENU on this link: the run stops and puts its start file back, which takes the camera out of that state.")


def chosen(doc: dict, path: list, option: str, within: bool = False) -> dict | None:
    """The known state a choice of `option` in the row `path` would set (states' entry), or None: the option and each
    label of the row compared as the kit compares option labels (camkit.match.key: case, spaces, dots and OCR
    look-alikes aside, "1 fps" and "Ifps" as "1fps"). within (kit/drive.py's Enter): `path` may also be a row above the
    state's, from which a run walks down to it."""
    from .match import key
    at = [key(p) for p in path or ()]
    for st in states(doc):
        row = [key(p) for p in st["row"].split(" > ")]
        if key(option) == key(st["label"]) and at and (at == row or (within and row[:len(at)] == at)):
            return st
    return None


def sets_state(doc: dict, path: list, option: str) -> str:
    """Why a choice of `option` in the row `path` (mode_switch --set's) would set a known state (chosen), or ""."""
    st = chosen(doc, path, option)
    if st is None:
        return ""
    return (f"--set {st['row']}={option}: {st['setting']} at {st['label']} in {st['mode']} mode is a state where this "
            f"camera has been seen to act on one button press twice ({st['seen']}): the kit never sets it, and nothing "
            "was sent to the camera")
