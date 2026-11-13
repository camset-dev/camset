"""The names the definition writer gives values: a reading cleaned of OCR slips and icon words, snapped to a name the
definition already uses, an option's sub-choice told apart from the option, one name for a value two options write
alike, and one name per code in a picker family; a checklist box's words for ticked and unticked."""
import difflib
import re
import unicodedata

from camkit import placement
from pass2_report import close

LATIN = str.maketrans("СсАаЕеОоРрТтНМВК", "CcAaEeOoPpTtHMBK")


def clean(label: str) -> str:
    """The camera's label without OCR slips: Cyrillic look-alikes, "lmg" for "Img", "O" for a leading
    zero before an arrow, and a space the camera does not put before "(" ("1(Not Locked On)")."""
    t = unicodedata.normalize("NFKC", str(label)).translate(LATIN).strip()
    t = re.sub(r"\blmg\.", "Img.", t)
    t = re.sub(r"^O(?=→)", "0", t)
    t = re.sub(r"^(\d+)\s+\(", r"\1(", t)
    t = re.sub(r":\s*\(No Import\)$", "", t)       # a User LUT slot's state after its name (2026-10-30)
    icon = icon_word(t)                            # the icon's word before the name: "LIGHT Light", "STD Standard"
    return icon[1] if icon else t


def squashed(label) -> str:
    """A label as compared with another the camera showed elsewhere, without case or spaces: a refusal's "Black &
    White" is the list's "Black&White" (PP10's Color Mode, two readers)."""
    return re.sub(r"\s+", "", clean(label)).lower()


def icon_word(t: str) -> tuple | None:
    """(icon, name) for a reading that is an icon's capitals and then the words they stand for ("X.FINE Extra fine",
    "STD Standard", "LIGHT Light": the icon's letters in order in the name's); None otherwise."""
    m = re.match(r"^([A-Z][A-Z.]+)\s+(\S.*)$", str(t))
    if not m:
        return None
    letters, it = m.group(1).replace(".", "").lower(), iter(re.sub(r"[^a-z]", "", m.group(2).lower()))
    return (m.group(1), m.group(2)) if len(letters) >= 2 and all(c in it for c in letters) else None


TICKED, UNTICKED = re.compile(r"allow|tick|\bon\b|target|includ|regist", re.I), re.compile(r"exclud|\boff\b|not", re.I)


def tick_values(proved: dict) -> tuple:
    """(value when ticked, value when unticked) from a checklist record's proofs ("Eye: ticked": 1)."""
    on = {v for lab, v in proved.items() if lab.endswith(": ticked")}
    off = {v for lab, v in proved.items() if lab.endswith(": unticked")}
    return (on.pop() if len(on) == 1 else None), (off.pop() if len(off) == 1 else None)


def check_labels(s: dict, proved: dict, changed: list):
    """A checklist box's record keeps the schema's words when they mean what the camera showed, and
    has them swapped when they say the opposite (Recog Trgt Select: Airplane, 2026-10-29: ticked
    wrote 1, the schema called 0 "Allowed (ticked)"). Returns "kept" when the schema's words stood."""
    on, off = tick_values(proved)
    if on is None or off is None:
        return
    labels = dict((v, lab) for v, lab in s.get("values") or [])
    lab_on, lab_off = labels.get(on, ""), labels.get(off, "")
    if TICKED.search(lab_on) and not UNTICKED.search(lab_on) and UNTICKED.search(lab_off):
        return "kept"                                     # agrees: the schema's words stand
    if TICKED.search(lab_off) and not UNTICKED.search(lab_off) and UNTICKED.search(lab_on):  # noqa: SIM108 (two long arms read apart)
        new = {on: lab_off, off: lab_on}                  # inverted: swap
    else:
        new = {on: "Ticked", off: "Not ticked"}
    for v in (on, off):
        if labels.get(v) != new[v]:
            changed.append((s["key"], s["name"], v, labels.get(v), new[v]))
            labels[v] = new[v]
    s["values"] = [[v, lab] for v, lab in sorted(labels.items())]


def snap(label: str, vocabulary: list) -> str:
    """A function's name read off a picker, replaced by the name the schema already uses for it
    anywhere when that is clearly the same text ("Subject Reccgnition AF", "faRegist. Face Priority"), and never one
    whose numbers differ, however alike the rest (snap never crosses a digit)."""
    key = lambda t: re.sub(r"[^a-z0-9★]", "", t.lower())
    digits = re.findall(r"\d+", label)
    # never across a digit: "Custom Look 1" and "Custom Look 2" are alike at 0.909 and two names
    vocabulary = [w for w in vocabulary if re.findall(r"\d+", w) == digits]
    best = max(vocabulary, key=lambda w: difflib.SequenceMatcher(None, key(w), key(label)).ratio(), default=None)
    if best and difflib.SequenceMatcher(None, key(best), key(label)).ratio() >= 0.9:
        return best
    return label


def axis_tail_out(label: str, v, s: dict, subs: list, axes: set, row: str, labels: dict) -> str:
    """An option read with its sub-choice's value at proof time ("Self-timer(Single): 5 sec", the delay 0x04c0 holds)
    as the option alone ("Self-timer(Single)"): the tail goes when the row has a setting placed under that option
    (`subs`, under_option the name or the whole label; its labels hold the tail, or not) or an axis proof for it
    (`axes`: (row, option)), and no other value of the record is named by the option ("Spot: XL" and "Spot: L" are two
    values: their tails stay). The tail can be the camera's own setting at proof time (decision 16)."""
    if ":" not in label:
        return label
    name = label.split(":", 1)[0].strip()
    if any(str(lab).startswith(name) for w, lab in labels.items() if w != v and lab):
        return label
    placed = [t for t in subs if t.get("under_option") in (name, label) and t.get("row") == s.get("row")
              and t["key"] != s["key"]]
    return name if placed or (row.split(" [")[0], name) in axes else label


def same_option(a: str, b: str) -> bool:
    """Two names of one option, word by word, each word of one the start of the other's ("Cont. Shooting" and
    "Continuous Shooting", as the report's abbreviation rule reads them)."""
    wa, wb = (re.findall(r"[a-z0-9+]+", str(x).lower()) for x in (a, b))
    return bool(wa) and len(wa) == len(wb) and all(x == y or (not x.isdigit() and not y.isdigit()
                                                            and (x.startswith(y) or y.startswith(x))) for x, y in zip(wa, wb, strict=True))


def option_prefix_out(label: str, options: set) -> str:
    """A sub-choice's label without its option's name before it ("Cont. Shooting: Hi" under Continuous Shooting is
    "Hi"): the axis_tail_out rule the other way round. `options`: the names the setting's option goes by."""
    if not isinstance(label, str) or ": " not in label:
        return label
    head, tail = (x.strip() for x in label.split(": ", 1))
    return tail if tail and any(same_option(head, o) for o in options) else label


def one_name(labels) -> str:
    """One name for a value two options write the same way ("HEIF(4:2:0)" and "HEIF(4:2:2)" both store 4): their
    common start, cut back to a word ("HEIF"), when it holds two characters or more and is not a bare number; else
    the names joined with " / "."""
    labels = sorted({str(x) for x in labels})
    if len(labels) == 1:
        return labels[0]
    full = max(labels, key=lambda x: (len(placement.norm(x)), x))
    initials = "".join(w[0] for w in re.findall(r"[a-z0-9]+", full.lower()))
    if all(x == full or same_option(x, full) or (placement.norm(x) and initials.startswith(placement.norm(x)))
           for x in labels):
        return full                      # the others abbreviate it: "P" is "Program Auto", "Cont." "Continuous"
    p = labels[0]
    for x in labels[1:]:
        while not x.startswith(p):
            p = p[:-1]
    if any(len(x) > len(p) and x[len(p)].isalnum() and p[-1:].isalnum() for x in labels) or \
            any(len(x) > len(p) and not re.match(r"[\s(]", x[len(p)]) for x in labels):
        cut = max(p.rfind(" "), p.rfind("("))
        p = p[:cut] if cut > 0 else ""
    p = p.rstrip(" (:-/.,")
    if len(p) >= 2 and not re.fullmatch(r"[\d.\s+-]+", p):
        return p
    return " / ".join(labels)


PICKER_FAMILY = re.compile(r"(Fn Menu \((?:Still|Movie|Playback)\)|Custom Key \((?:Still|Movie|Playback)\)|My Dial) ?\d*:")


def picker_family(name: str) -> str | None:
    """The picker a setting is a slot of ("Custom Key (Still)" for "Custom Key (Still): AEL Button"): the slots of one
    family choose from one screen's list of functions, so a code has one name in all of them."""
    m = PICKER_FAMILY.match(name or "")
    return m.group(1) if m else None


def family_name(names: dict, reads: dict) -> str:
    """One name for a code of a picker family, from the names its slots give it ({name: (slots, full slots)}) and the
    names the camera's screens were read as ({name: best reader source}). A name loses when it is another one with a
    head the camera never showed ("Custom Key Zoom: Fixed Speed STBY" beside "Fixed Speed STBY": the screen shows an
    icon, not the words), the start of another ("Face Priority in Multi M"), or an OCR slip of a fuller one ("Fixed
    Speed SBY" for "Fixed Speed STBY"); of the rest, the one two readers agreed on, then one read on the camera at
    all, then the one in more slots proved in full, then in more slots."""
    left = set(names)
    shown = " ".join(placement.norm(r) for r in reads)
    n = placement.norm
    for a in sorted(names):
        for b in sorted(names):
            if a == b or a not in left:
                continue
            head = a.split(": ", 1)
            unshown_head = len(head) == 2 and head[1] == b and n(head[0]) not in shown
            start_of = n(a) != n(b) and n(b).startswith(n(a))
            if unshown_head or start_of or (n(a) != n(b) and close(a, b) >= 0.75 and len(n(a)) < len(n(b))
                                            and not n(b).startswith(n(a)) and not b.endswith(": " + a)
                                            and reads.get(a) != "two readers"):          # an OCR slip of a fuller one
                left.discard(a)
    rank = {"two readers": 3, "vision model": 2, "one reader": 1}
    return max(sorted(left or names), key=lambda x: (rank.get(reads.get(x), 0), x in reads, names[x][1], names[x][0]))


# the exposure modes' names and the letters a mode dial and older names give them: photography's own words, no
# camera's (a value still named by its letter beside the names takes the name: schema_update)
MODE_LETTERS = {"Program Auto": "P", "Aperture Priority": "A", "Shutter Priority": "S", "Manual Exposure": "M"}


def ev_label(v: int) -> str:
    """A quarter-stop count from 20 (down is plus) as the camera shows it: halves, else thirds."""
    ev = (20 - v) / 4
    ev = ev if (ev * 2).is_integer() else round(ev * 3) / 3
    return f"{ev:+.1f} EV"


def value_order(v) -> tuple:
    return (0, v, "") if isinstance(v, (int, float)) else (1, 0, str(v))
