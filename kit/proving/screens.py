"""Reading what the camera's screen shows: the label under the cursor bar (OCR, the vision model as the decider),
a carousel's title and its second axis's strip, a row found by its label, the cursor's place without text, and the
notices a choice can bring up (the camera's refusal, a one-time explanation, an information notice taken with its
OK)."""
import difflib
import os
import re
from pathlib import Path

import numpy as np

from camkit import match, ocr, safety, screen
from camkit.vlm import PROMPTS, ask_role
from page_model import key_text, same_text
from runner import INFO_OK_SLACK, joined, notice_words

from .base import Blocked, Failed

BAR_X = {"menu": (140, 470), "submenu": (55, 470), "list": (110, 556),   # label crops, as in pass 1
         "picker": (370, 636)}                                            # the function picker, right of its radio


def refuse_or_fail(cam, name: str, what: str):
    """Right did not open the row's screen. The camera's own refusal ("not available as follows Gamma
    HLG2": PP10's Black Gamma, 2026-10-29) is OKed and raised as Blocked; anything else is Failed."""
    s = cam.read()
    if s.kind == "notice":
        text = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
        if re.search(r"not available", text, re.I) and not safety.confirmation(text):
            reason = re.sub(r"\s+", " ", text.split("as follows", 1)[-1])
            reason = re.sub(r"[\s•●]*(\bOK\b)?[\s•●]*$", "", reason).strip()     # the OK button and its dot
            reason = re.sub(r"^\W+", "", reason)                             # an icon read as "%"
            cam.press("enter")                  # an information notice: OK goes back to the row
            raise Blocked(f"{name}: blocked by {reason!r}", reason)
    raise Failed(f"{name}: Right opened {s.kind}, {what}")


def first_time_notice(cam) -> bool:
    """A screen the camera explains once before it opens (Custom Key/Dial Set. after a settings reset: "In the next
    setting screen, you can check the function assigned to a specific button by pressing that button on the device",
    with "Don't show this again" and OK, 2026-11-07). The cursor sits on the tick box: Down to OK, Enter, and the
    screen behind it opens. The box is never ticked (that would be a setting changed for a proof). False for any
    other screen, which is left as it is."""
    text = ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path], (0, 0, 640, 480))
    if not re.search(r"show this again", text, re.I) or safety.confirmation(text):
        return False
    cam.press("down")
    cam.press("enter")
    return True


def bar_text(cam) -> str:
    """OCR of the label under the cursor bar (menu row, submenu row, list option)."""
    s, f = cam.read(), cam.frame
    if not s.bar or s.kind not in BAR_X:
        return ""
    x0, x1 = BAR_X[s.kind]
    pad = -2 if s.kind == "list" else 0
    t = ocr.text_in(ocr.read([f.path])[f.path], (x0, s.bar[0] - pad, x1, s.bar[1] + pad)).strip(" •")
    return re.sub(r"\s+[oO0]$", "", t)              # the radio circle OCR reads as a letter


def option_key(t: str) -> str:
    """Option labels compared without case, spaces, dots or OCR look-alikes, keeping a leading
    number (page_model.key_text drops "1 " in "1 Sec" as if it were an icon). A Cyrillic look-alike
    is its Latin letter ("С.Temp./Filter", 2026-10-31). The rules live in camkit/match.py."""
    return match.key(t)


def main_name(label: str, kind: str) -> str:
    """A carousel option's name without its second-axis value ("Continuous Shooting: Mid" ->
    "Continuous Shooting"): the value shown depends on what was chosen there last."""
    return label.split(":", 1)[0] if kind == "dialog" else label


def carousel_text(cam) -> str:
    """OCR of the orange line under a carousel's title: the option under the cursor (pass 1's crop)."""
    f = cam.frame
    return ocr.text_in(ocr.read([f.path])[f.path], (110, 60, 636, 112)).strip()


def _matches(t: str, labels) -> list:
    hits = [i for i, l in enumerate(labels) if option_key(l) == option_key(t)]
    if not hits:        # the saved option's radio circle read as a letter in front ("03" for "3")
        t2 = re.sub(r"^[oO0]\s*", "", t)
        hits = [i for i, l in enumerate(labels) if t2 != t and option_key(l) == option_key(t2)]
    if not hits:        # an icon read as letters in front ("SAF..."); never between near-twins (0.7 / 0.07 s)
        hits = [i for i, l in enumerate(labels) if same_text(t, l)]
    return hits


def option_answer(cam) -> dict | None:
    """The vision model's whole answer about the option under the cursor on the frame on screen (PROMPTS["option"]:
    "title", "selected", "value"); None when the reader fails or answers anything but an object. kit/provers/
    scale_run.py reads a scale's number from it, which can come in "value" with "selected" empty (2026-11-10)."""
    try:
        v = ask_second(cam.frame.path.read_bytes(), PROMPTS["option"], timeout=25)
    except Exception:
        return None
    return v if isinstance(v, dict) else None


def vlm_option(cam) -> str:
    """The vision model's reading of the option under the cursor (its answer's "selected", option_answer): the decider
    where OCR is unsure (short numbers, lost signs), and a second reading kept with every proof (user, 2026-10-29: use
    vLLM all the time if it makes sense; ~1 s a call)."""
    v = option_answer(cam)
    return str(v.get("selected") or "") if v else ""


def ask_second(image: bytes, prompt: str, timeout: float) -> dict:
    """The "second" reader's answer; when it will not connect, the next configured reader that answers takes the
    role for the rest of the run: camkit.vlm.ask_role, through which every question a run asks about a frame goes
    (camkit.live asks it so too)."""
    return ask_role("second", image, prompt, timeout)


# A carousel option's second axis drawn as a strip of cells under the dialog's body, between its ◂ ▸ (screen.GLYPHS'
# strip_left and strip_right): Focus Area's Spot sizes and Custom 1-3 as filled cells, the lit one orange with dark
# text, and Tracking's areas as an icon with the size or "C1" after it, the lit one drawn orange (the a1 II:
# runs/<model>_fw<fw>/kit2_afreg2 00204_reread.png and 00206_reread.png, kit2_axes 00341_reread.png). Five places
# 87.5 px apart with the lit cell in the middle one; the cells right of it are the values Right comes to next, in
# turn, and those left of it the values Left does (a short list leaves the places past its ends empty). The lit cell is
# looked for in AXIS_STRIP, the cells' text read on the line AXIS_TEXT_Y (a frame's corner drawn in the strip, above or
# below the text, stays out: kit2_afreg2 00206, kit2_axes 00320)
AXIS_STRIP = (158, 322, 597, 394)
AXIS_TEXT_Y = (347, 368)
AXIS_PITCH = 87.5
# the short text a value's cell shows: "Spot: L" and "Tracking: Spot L" show "L" (the axis walk's "Tracking: SpotS"
# shows "S"), "Custom 3" and "Tracking: Custom 3" show "C3"; Wide, Zone, Center Fix and Expand Spot show an icon alone
CELL_SIZE = re.compile(r"(?:spot\s*)?(xs|s|m|l|xl)", re.I)
CELL_CUSTOM = re.compile(r"custom\s*(\d)", re.I)
# a reading that is a cell's short text alone: after the cell's icon read as signs ("#C1", "••• M", "®*ХS"), with a dot
# after it ("XL."), Cyrillic look-alikes ("СЗ") and "(" for C ("(1", RapidOCR); never with a letter before it or a sign
# after it ("EСЗ", or "L ]": Center Fix's [ ] read as an L, kit2_axes 00356_right.png)
CELL_TEXT = re.compile(r"[^A-Z0-9]*(C[1-9]|XS|XL|S|M|L)[\s.]*")
CELL_LOOKALIKES = str.maketrans("СсЗзХхМмЅѕ(", "CC33XXMMSSC")


def cell_code(label) -> str | None:
    """The short text an axis value's cell shows ("Custom 3" -> "C3", "Tracking: Spot L" -> "L"); None for a value
    whose cell is an icon alone."""
    tail = str(label or "").split(":", 1)[-1].strip()
    if m := CELL_SIZE.fullmatch(tail):
        return m[1].upper()
    m = CELL_CUSTOM.fullmatch(tail)
    return f"C{m[1]}" if m else None


def cell_text_code(text) -> str | None:
    """The cell's short text a reading of it is (CELL_TEXT), or None."""
    m = CELL_TEXT.fullmatch(str(text or "").translate(CELL_LOOKALIKES).upper())
    return m[1] if m else None


def axis_lit_x(image) -> float | None:
    """Centre x of the axis strip's lit cell: its orange (screen's mask, closed as camkit.live closes a lit item's, so a
    cell's fill, or its letters and icon, are one region), the regions within a cell's width of the largest; None when
    no orange there could be a cell (a strip greyed with its option, kit2_afreg2 00300_reread.png, draws its lit cell
    dark red), or orange of note lies outside that cell."""
    import cv2
    from camkit.live import CLOSE
    x0, y0, x1, y1 = AXIS_STRIP
    o = screen._orange(image)[y0:y1, x0:x1].astype(np.uint8)
    closed = cv2.morphologyEx(o, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, CLOSE))
    n, lab, st, _ = cv2.connectedComponentsWithStats(closed, connectivity=8)
    regions = [(int(st[i, 0]), int(st[i, 0] + st[i, 2]), int(o[lab == i].sum())) for i in range(1, n)]
    regions = [r for r in regions if r[2] >= 8]                 # a speck: a frame's corner blended over a cell
    if not regions:
        return None
    big = max(regions, key=lambda r: r[2])
    cell = [r for r in regions if max(r[1], big[1]) - min(r[0], big[0]) <= 0.7 * AXIS_PITCH]
    lit = sum(r[2] for r in cell)
    if lit < 40 or sum(r[2] for r in regions if r not in cell) > 0.25 * lit:
        return None
    return x0 + (min(r[0] for r in cell) + max(r[1] for r in cell)) / 2


def axis_cells(f, lit_x: float) -> list:
    """[(reader, text, offset)]: each reading of a strip cell's short text alone (cell_text_code) on frame f, by the
    configured OCR engine and the second one where installed, with its place counted from the lit cell (0 the lit one,
    1 the next right, -1 the next left); a reading off the cells' text line or between two places is left out."""
    x0, _, x1, _ = AXIS_STRIP
    out = []
    for eng in [ocr.engine()] + ([ocr.second()] if ocr.second() else []):
        for ln in ocr.read([f.path], eng=eng)[f.path]:
            cx, cy = ln.x + ln.w / 2, ln.y + ln.h / 2
            if not (x0 <= cx <= x1 and AXIS_TEXT_Y[0] <= cy <= AXIS_TEXT_Y[1]) or ln.w > 1.2 * AXIS_PITCH:
                continue
            k = round((cx - lit_x) / AXIS_PITCH)
            if abs(cx - lit_x - k * AXIS_PITCH) <= 0.3 * AXIS_PITCH and abs(k) <= 2 and cell_text_code(ln.text):
                out.append((eng, ln.text, k))
    return out


def strip_value(cam, vals: list, title: str, vlm: str = "") -> tuple:
    """(index into vals or None, how it was read) of the axis value the strip's lit cell shows, for a title that names
    none ("Customß 7": the Custom 3 box's corner drawn over the title, kit2_pass2 234940_reread.png and kit2_afreg2
    00206_reread.png). Only when the title still reads as the option's (it starts as every value does: "custom",
    "spot:", "tracking:"), so a Custom cell's "C3" is never Tracking's "Tracking: Custom 3", and the strip has its lit
    cell (axis_lit_x). Each reading of a cell's short text (axis_cells, and the vision model's reading, which often is
    the lit cell's: "C3") names a value, and with its place one for the lit cell: "C2" one left of it is the value after
    Custom 2, Custom 3. Every reading must name the same one, and none a short text no value of the axis has; how is
    {"read_by": "axis cell", "cell_readings": [{"reader", "text", "offset"}]}, else {}. An axis whose cells are all
    icons, as most are, is never read so (nothing is read off its frame)."""
    codes = {}
    for j, v in enumerate(vals):
        if c := cell_code(v):
            codes.setdefault(c, []).append(j)
    lead = os.path.commonprefix([option_key(v) for v in vals])
    if not codes or len(lead) < 3 or not option_key(title).startswith(lead):
        return None, {}
    lit_x = axis_lit_x(cam.frame.image)
    if lit_x is None:
        return None, {}
    readings = axis_cells(cam.frame, lit_x) + ([("vlm", vlm, 0)] if cell_text_code(vlm) else [])
    named = set()
    for _, text, k in readings:
        js = codes.get(cell_text_code(text)) or []
        if len(js) != 1:
            return None, {}                 # a short text the axis does not have, or has twice: not this strip
        named.add((js[0] - k) % len(vals))
    if len(named) != 1:
        return None, {}
    return named.pop(), {"read_by": "axis cell",
                         "cell_readings": [{"reader": r, "text": t, "offset": k} for r, t, k in readings]}


SEEN: dict = {}                  # row label -> how OCR reads it on the camera ("Fixed Speed SBY" for STBY)


def keeps_lead(reading: str, label: str) -> bool:
    """A label's short first word ("Av", "Tv") must be in the reading too: label cleaning drops it as
    an icon, so "Tv Auto/Manual Switch" passed for "Av Auto/Manual Switch" and the Tv proofs were
    made on the Av row (2026-10-31). An icon glued on in front still passes ("SAF Frame" for "AF Frame").
    Before a bracket the camera may drop the space: "Lo(E-Shutter)" for "Lo (E-Shutter)" (2026-11-01)."""
    m = re.match(r"([A-Za-z0-9]{1,2})\s+(?=[A-Z(])", (label or "").strip())
    return m is None or re.search(rf"{re.escape(m.group(1).lower())}[\s(]", (reading or "").lower()) is not None


def glued(label: str) -> str:
    """A short first word glued to its bracket, as the camera shows it: "Lo (E-Shutter)" is
    "Lo(E-Shutter)" on screen, and label cleaning drops a short word before a space as an icon, which
    left "(e-shutter)" for all four speed rows (2026-11-01)."""
    return re.sub(r"^([A-Za-z0-9+]{1,3})\s+\(", r"\1(", (label or "").strip())


def at_label(cam, kind, label) -> bool:
    if cam.read().kind != kind:
        return False
    t = bar_text(cam)
    return (same_text(t, glued(label)) and keeps_lead(t, label)) or (label in SEEN and same_text(t, SEEN[label]))


def closest_row(texts: list, label) -> int | None:
    """The one reading in a lap of rows that is clearly the label's: the only one ending with the
    whole label (its icon read as a word in front: "uir Rear Dial R", too close to "t7Rear Dial L" by
    ratio, 2026-10-31), else the closest when clearly closer than every other."""
    k = key_text(label)
    ends = [i for i, t in enumerate(texts) if len(k) >= 4 and key_text(t).endswith(k) and len(key_text(t)) - len(k) <= 4]
    if len(ends) == 1:
        return ends[0]
    score = sorted(((difflib.SequenceMatcher(None, key_text(t), key_text(label)).ratio(), i) for i, t in enumerate(texts)),
                   reverse=True)
    if not score or score[0][0] < 0.8 or (len(score) > 1 and score[0][0] - score[1][0] < 0.1):
        return None
    return score[0][1]


def place(cam) -> tuple:
    """Where the cursor is, without reading text: screen type, page (breadcrumb picture), cursor row.
    OCR reads some labels several ways ("Fixed Speed STBY" / "SBY" / "siBy", 2026-10-29)."""
    s = cam.read()
    return s.kind, screen.page_bits(cam.frame.image), s.row


def same_place(a, b, tol: int = 2) -> bool:
    """Same screen type and cursor row, page pictures within `tol` cells (packed bits)."""
    if a is None or b is None or a[0] != b[0] or a[2] != b[2]:
        return False
    return sum(bin(x ^ y).count("1") for pa, pb in zip(a[1], b[1], strict=True) for x, y in zip(pa.tobytes(), pb.tobytes(), strict=True)) <= tol


def run_tmp_png(f):
    """A frame grabbed without saving, written to a temporary file for OCR (one per process: two runs at once never
    read each other's frame); the caller removes it once read."""
    import tempfile
    from PIL import Image
    path = Path(tempfile.gettempdir()) / f"camkit_notice_{os.getpid()}.png"
    Image.fromarray(f.image).save(path)
    return path


def notice_focus(img):
    """The notice's orange-filled bar (x, y, w, h), anywhere on the screen: its OK can sit below the
    band the menu readers look in (y 404-460 under a "Don't show this again." box)."""
    import cv2
    _, _, st, _ = cv2.connectedComponentsWithStats(screen._orange(img).astype(np.uint8), connectivity=8)
    bars = [(int(x), int(y), int(w), int(h)) for x, y, w, h, a in st[1:] if 40 <= h <= 66 and w >= 120 and a / (w * h) > 0.6]
    return max(bars, key=lambda b: b[2] * b[3]) if bars else None


def info_notice_ok(cam, name: str, kinds: tuple = ("notice", "unknown"), words: bool = True) -> dict | None:
    """An information notice after a choice ("You can perform detailed settings ... Select on Cam &
    Send", with a "Don't show this again." box above its OK, after Send (This Image) on a playback Fn
    tile, 2026-10-29): Down to its OK, never ticking the box, and OK. Anything that reads like a
    confirmation, or a cursor that is not on OK, fails the cell. None when no notice is up (the screen is not one
    of `kinds`: a list prover passes "table" for an information screen with buttons, Exposure Ctrl Type's). words
    False: what the screen reads is neither printed nor put in a failure's message (the frame is named; the caller
    keeps the words where it keeps a notice's), for a setup step whose screen can show the owner's values."""
    if cam.read().kind not in kinds:
        return None
    lines = ocr.read([cam.frame.path])[cam.frame.path]
    text = ocr.text_in(lines, (0, 0, 640, 480))
    said = f": {text[:80]!r}" if words else ""
    if not text or safety.confirmation(text) or not re.search(r"\bOK\b", text):
        raise Failed(f"{name}: a notice came up ({cam.frame.path.name}){said}")
    for _ in range(3):
        focused = notice_lit(cam)
        if re.fullmatch(r"\W*OK\W*", focused or ""):
            if words:
                print(f"   information after the choice, taken with its OK: {text[:70]!r}", flush=True)
            cam.press("enter")
            return {"text": text, "frame": cam.frame.path.name}
        if not re.search(r"don.?t show", focused or "", re.I):
            break
        cam.press("down")                    # off the "Don't show this again." box, never Enter on it
    raise Failed(f"{name}: the notice's OK could not be reached ({cam.frame.path.name}){said}")


def notice_lit(cam) -> str:
    """OCR of the notice's lit (orange-filled) bar on the frame on screen (notice_focus), "" when none is lit."""
    box = notice_focus(cam.frame.image)
    return ocr.text_in(ocr.read([cam.frame.path])[cam.frame.path],
                       (box[0], box[1], box[0] + box[2], box[1] + box[3])) if box else ""


# a line of a notice that is a button's word alone (safety.BUTTON_WORDS), its dot or bullet aside: a notice passed with
# --info-ok has one, its OK
BUTTON_LINE = re.compile(r"[\s•●.]*(" + "|".join(sorted(safety.BUTTON_WORDS)) + r")[\s•●.]*", re.I)
# what no line of such a notice but its OK may say, in any reading of the line (safety.readings): a second button, read
# whole or not ("Cance1", "x Cancel", "Back"), or a word of a choice or an action, inflected too ("Apply", "deleted",
# "overwritten", "Executed.")
NOT_BESIDE_OK = re.compile(r"canc|\b(?:yes|no|back|close|execute|enter|start|apply|register|proceed|continue|confirm|"
                           r"delete|format|reset|overwrit|eras|initiali[sz])")


def _confirm_names() -> tuple:
    """safety.confirmation's own words as written ("delete", "all data", "initialize" and "initialise", "reset"), for
    joined: the same list, never a copy of it."""
    out = []
    for word in re.sub(r"^\\b\(|\)\\b$", "", safety._CONFIRM_RE.pattern).split("|"):
        out += [word.replace("[sz]", "s"), word.replace("[sz]", "z")] if "[sz]" in word else [re.sub(r"s\?$", "", word)]
    return tuple(dict.fromkeys(out))


# safety.confirmation's words run together inside one word of the notice ("Deleteall", "Willbelost"; runner.joined, which
# takes no name read across two words: "camera settings", "presets", "lens end"): a local check until the guards judge
# words run together themselves
CONFIRM_NAMES = _confirm_names()
# a "Don't show this again." box's line, word for word (word_cover's slips allowed), which the phrase need not name
DONT_SHOW_WORDS = ("don't", "show", "this", "again")
# what an icon glued to a line's first or last word is never taken for: letters that would negate it ("unset",
# "isnt" read without its apostrophe)
NEGATING_BEFORE, NEGATING_AFTER = frozenset({"un", "in", "im", "il", "ir", "no"}), frozenset({"n", "nt"})
OK_BAND = 4          # px: a line whose middle is lower than this above the OK line's top sits on or below the OK's band


def letters(word: str) -> int:
    """The letters and digits of a word (an apostrophe inside it is none)."""
    return sum(c.isalnum() for c in word)


def word_cover(w: str, t: str, edge: bool = False) -> int | None:
    """How many letters of the notice's word `t` the phrase's word `w` accounts for, or None when it is not that word: the
    word as it stands; for a word of four letters or more, one letter read for another, dropped or put in
    (safety.one_apart: that letter is not accounted for); or, for a word of two letters or more that is the first or the
    last of its line (`edge`, where an icon sits beside the text), the word with one or two letters or digits glued on
    before or after it, never ones that negate it (NEGATING_BEFORE, NEGATING_AFTER): those are not accounted for."""
    if t == w:
        return letters(w)
    if letters(w) >= 4 and safety.one_apart(t, w):
        return min(letters(t), letters(w)) - (len(t) == len(w))
    if edge and letters(w) >= 2 and 0 < len(t) - len(w) <= 2:
        glued = t[:len(t) - len(w)] if t.endswith(w) else t[len(w):] if t.startswith(w) else ""
        if glued.isalnum() and glued not in (NEGATING_BEFORE if t.endswith(w) else NEGATING_AFTER):
            return letters(w)
    return None


def dont_show(ln) -> bool:
    """Whether an OCR line is a "Don't show this again." box's line and nothing else (DONT_SHOW_WORDS, word by word,
    word_cover's slips allowed: "Dont show this again")."""
    got = notice_words(ln.text).split()
    return len(got) == len(DONT_SHOW_WORDS) and all(word_cover(w, t) is not None
                                                    for w, t in zip(DONT_SHOW_WORDS, got, strict=True))


def notice_cover(phrase: str, lines: list) -> tuple | None:
    """How the phrase's words (`phrase`, runner.notice_words) account for a notice's lines (OCR lines, its OK and its
    "Don't show this again." line left out): None when its words are not all found in the lines' words, in order (each by
    word_cover); else (the letters and digits of the lines left unaccounted for, why the phrase does not account for the
    notice, "" where it does). It does not where a word it skips has three letters or more (an icon is read as a letter or
    two: "Stop", "Later" or a sentence is no icon), or where a line that holds none of its words lies outside the lines
    that hold them (a mark or a stray letter stacked above the OK)."""
    seen = []                                       # (line, word, the line's first or last word)
    for k, ln in enumerate(lines):
        got = notice_words(ln.text).split()
        seen += [(k, t, j in (0, len(got) - 1)) for j, t in enumerate(got)]
    matched, covered, i = set(), 0, 0
    for w in phrase.split():
        while i < len(seen):
            got = word_cover(w, seen[i][1], seen[i][2])
            i += 1
            if got is not None:
                covered += got
                matched.add(i - 1)
                break
        else:
            return None
    left_over = sum(letters(t) for _, t, _ in seen) - covered
    if any(letters(t) >= 3 for j, (_, t, _) in enumerate(seen) if j not in matched):
        return left_over, "a word it does not name"
    held = {seen[j][0] for j in matched}
    top = min((lines[k].y for k in held), default=0)
    bottom = max((lines[k].y + lines[k].h for k in held), default=0)
    if any(not top <= ln.y + ln.h / 2 <= bottom for k, ln in enumerate(lines) if k not in held):
        return left_over, "a line outside its text"
    return left_over, ""


def pass_named_notice(cam, name: str, phrase: str, lit_before: str, words: bool = True) -> dict:
    """--info-ok (runner.info_ok_or_exit): the information notice Right opened on the row `name` ("A > B" for a submenu's
    row) taken with its OK, so the screen behind it opens (Different Set for Still/Mv on the a1 II: "You can set
    different settings for still image mode and movie mode in the next screen. The setting set for ☑ is independent.",
    a single OK, 2026-11-03). Only for a notice that explains and asks nothing, whose whole text the run gives
    (`phrase`, runner.notice_words: letters, digits and single spaces; punctuation and glyphs ignored in both). Enter goes
    out once, and only when all hold:
    - the screen is a notice;
    - the lit bar read before Right (`lit_before`) is the row's last label (safety.bar_on_row, or page_model.same_text
      with its short first word kept: keeps_lead);
    - the phrase's words are found in the notice's lines, in order (notice_cover), its OK line aside, and a line that
      says "Don't show this again." and nothing else (dont_show), unless the phrase names its words too;
    - no reading of the text holds a question mark;
    - it reads as no confirmation (safety.confirmation, and its words run together: runner.joined), names nothing the
      never-open list holds (safety.screen_refused) and nothing of identity or credentials (safety.identity_screen);
    - exactly one of its lines is a button's word alone, and that word is OK (BUTTON_LINE);
    - no other line names a second button, a choice or an action in any reading (NOT_BESIDE_OK), and none sits on or
      below the OK line's band (OK_BAND);
    - the phrase accounts for the whole notice (notice_cover): no word of three letters or more it skips, no line
      outside its text that holds none of its words, and at most runner.INFO_OK_SLACK of its letters and digits left over
      (an icon read as a letter or two, a slip), so no sentence or button the phrase does not name can ride along;
    - the lit button reads OK (notice_lit), and info_notice_ok, which judges it so too, presses the Enter.
    Returns {"row", "frame": the notice's frame} once passed, else {"refused": why} with nothing pressed; no text read
    off the screen is in either. Where the phrase leaves more of the notice over, the notice's text is printed (`words`:
    False on a run that withholds what it reads), so that its whole text can be given."""
    frame = cam.frame.path.name
    if cam.read().kind != "notice":
        return {"refused": f"not a notice ({cam.read().kind}, {frame})"}
    row = name.split(" > ")[-1]
    if not (safety.bar_on_row(lit_before, row) or (same_text(lit_before, row) and keeps_lead(lit_before, row))):
        return {"refused": "the lit bar read before Right is not the row named"}
    lines = ocr.read([cam.frame.path])[cam.frame.path]
    text = " ".join(ln.text for ln in lines).strip()

    def an_ok(ln) -> bool:
        m = BUTTON_LINE.fullmatch(ln.text or "")
        return bool(m) and m[1].lower() == "ok"
    said = [ln for ln in lines if not an_ok(ln)]
    aside = [ln for ln in said if not dont_show(ln)]
    cover = notice_cover(phrase, aside)
    if cover is None and len(aside) < len(said):
        cover = notice_cover(phrase, said)          # a phrase that names the box's words too
    if cover is None:
        return {"refused": f"not the notice named ({frame})"}
    if any(q in r for r in safety.readings(text) for q in "?？"):
        return {"refused": f"it asks a question ({frame})"}
    for check, why in ((safety.confirmation, "it reads as a confirmation"),
                       (lambda t: joined(t, CONFIRM_NAMES), "it reads as a confirmation, its words run together"),
                       (safety.screen_refused, "it names what the never-open list holds"),
                       (safety.identity_screen, "it names identity or credentials")):
        if check(text):
            return {"refused": f"{why} ({frame})"}
    buttons = [ln for ln in lines if BUTTON_LINE.fullmatch(ln.text or "")]
    if [BUTTON_LINE.fullmatch(ln.text)[1].lower() for ln in buttons] != ["ok"]:
        return {"refused": f"not a single OK: {len(buttons)} button lines ({frame})"}
    ok_line = buttons[0]
    others = [ln for ln in lines if ln is not ok_line]
    if any(NOT_BESIDE_OK.search(r) for ln in others for r in safety.readings(ln.text)):
        return {"refused": f"a line beside its OK names a button, a choice or an action ({frame})"}
    if any(ln.y + ln.h / 2 >= ok_line.y - OK_BAND for ln in others):
        return {"refused": f"a line sits on or below its OK's band ({frame})"}
    left_over, why = cover
    if why or left_over > INFO_OK_SLACK:
        if words:
            print(f"   the notice reads {text!r}: give its whole text as written with --info-ok", flush=True)
        return {"refused": f"the notice has {left_over} letters or digits beyond the phrase{f', {why}' if why else ''}: "
                           f"give its whole text as written ({frame})"}
    if not re.fullmatch(r"\W*OK\W*", notice_lit(cam) or ""):
        return {"refused": f"the lit button is not OK ({frame})"}
    try:
        if info_notice_ok(cam, name, kinds=("notice",), words=False) is None:
            return {"refused": f"no notice was up for its OK ({frame})"}
    except Failed:
        return {"refused": f"its OK could not be taken ({frame})"}
    return {"row": name, "frame": frame}
