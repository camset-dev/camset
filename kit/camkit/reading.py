"""One rule for reading the camera's screen: when OCR alone is trusted, and when the reader must be asked
(docs/decisions/0022, the owner's rule of 2026-11-13: "a reader is required, preferred a VLM and OCR backup").

    canonical(text)                       the one cleaning every reading gets before it is compared
    doubts(text, expect, ...)             why an OCR reading is not plain enough to be trusted alone ([] when it is)
    agree(a, b, expect, choices)          whether two readings name the same thing, by the kind of thing expected
    outcome(ocr_text, said, expect, ...)  what OCR's reading and the reader's make of a reading (pure)
    tally(votes, expect, choices)         the reading two or more independent votes name, if any (pure)
    check_engines()                       the OCR engines a run would use, refused at its start if one is unknown
    read(frame, where, expect, stakes)    one reading of one region of a frame by the rule: OCR, the reader on a
                                          doubt (or always, for a press or a proof), a fresh frame and a third vote
                                          when they disagree, and what stands (Reading, with every Vote cast)

In plain words (the decision record says it in full):
  1. One cleaning for every reading (canonical): compatibility forms, Cyrillic, Greek and accented look-alikes become
     the Latin letters they are drawn as, every dash a hyphen, every run of spacing one space; case kept. The camera's
     menus are in English (docs/CAMERA_SUPPORT.md), so a non-Latin or accented letter is always a misread. The raw
     reading is kept beside the cleaned one.
  2. OCR alone is enough only for a plain reading: Latin letters, digits and the camera's own signs as read, four
     characters or more, naming exactly one of the options expected there.
  3. Everything else is a doubt (doubts): a character the cleaning changed, or a letter with no Latin twin; a number
     or code of three characters or fewer (and, counted apart, a word that short); a digit's look-alike letter beside a
     digit; nothing read where something is lit; a number with no digit; a reading that names no option, several, or
     one only loosely.
  4. On a doubt the reader is asked first, before any press, proof line, guess or failure; then the owner's tie-break
     (2026-11-13):
     - Two independent votes agree: the reading stands; no third vote.
     - OCR read nothing where something is lit, and the reader names exactly one expected option: it stands as one
       reader's reading, recorded so; for a press or a guard never on that alone (a second, independent vote is
       needed). With no options to name, a lone reader never stands, nor after OCR and the reader were apart on an
       earlier frame.
     - OCR and the reader name different things (or OCR's reading names no option and the reader's does): a fresh
       frame, and both asked again, where a plain OCR reading is one more vote and never ends the disagreement in
       OCR's favour; still apart, a third vote, independent of the first two (the second OCR engine, the site's own
       check, then a reader of another model, the "third" role); the reading stands only when two of the votes name the
       same expected option and nothing else is named as often, else it is refused naming every reading.
     - A vote counts once per source: one OCR engine is one vote whatever name it goes by (engine_of), and two readers
       of one model are one vote (tally). The reader does not win a disagreement by itself: measured on the first
       camera's proofs, where OCR's reading named no option the reader's option was sometimes another one, where OCR
       had read nothing it was not.
     - A plain OCR reading the reader contradicts is, for now, recorded and stands; it becomes a vote like any other
       once each kind of screen's question to the reader is fixed and the disagreement is measured low.
  5. A press or a proof frame is always read by the reader too, doubt or not, and every reading records which eyes
     voted on which frame and which agreed (Reading.votes, Reading.agreed, Reading.evidence).
  6. Guards keep their own rule and may only add refusals: every eye's reading on every frame is judged, the raw
     reading beside its canonical one and never the canonical alone (Reading.texts), and any one refusing refuses; any
     two eyes that read differently refuse, and no vote settles that; a guard is never read again on a fresh frame for
     a better answer. A guard refuses what no eye can read, a doubt the reader does not answer, and a lone reader's
     reading that no second, independent vote names too.
  7. A reader is required: it is never asked about a black frame, and with the reader unreachable a plain reading goes
     on, marked as OCR's alone, while a doubtful one is refused ("reader needed"); no other check stands in for it.

What is in place (2026-11-13): these functions, their tests (kit/tests/test_reading.py) and the measuring tool
kit/tools/reader_census.py, which replays doubts(), agree(), outcome() and tally() over runs already made. No caller
reads through this module yet: camkit.match, page_model.key_text, camkit.safety and the other look-alike tables still
compare as they did, and every run decides and presses as before. The callers move onto it site by site once the
census has measured what that changes; the tests already say where canonical differs from each old table.

The eyes go through one seam each, so that a test fakes them in one place (kit/tests/conftest.py, eyes):
  _ocr_lines(frame, eng)                       camkit.ocr.read on the frame's file (eng: the second engine)
  _reader_answer(image, question, timeout, role)  camkit.vlm.ask_role(role, ...) for "second" or "third", a stand-in
                                               taking the role when that reader will not connect; gives the answer
                                               and the reader's name and model
  _reader_model(role)                          the model a role's reader would answer with, or None (no such reader)
Votes are told apart by their source: "ocr:<engine>", the engine name camkit.ocr.read runs (engine_of: "apple" or
"rapidocr", any other name refused), and "reader:<model>", the model id trimmed and case-folded (model_id); the same
weights under two ids cannot be told apart and count as two.
ask() wraps the reader with a memo for the process (the role, the frame's bytes and the question), never asks about a
black frame (camkit.live.black), and keeps a latch per role: after DOWN_AFTER failures in a row the reader counts as
unreachable for DOWN_FOR seconds, so a server that is off costs a run one timeout, not one per doubt.
(camkit.vlm.ask_role brings in a stand-in only on a refused connection; a read that times out is a failure here like
any other.)

This file holds no character outside ASCII: the look-alike letters are written as escapes, each with its Unicode name,
so that neither a reader of the file nor an OCR of it takes one for its Latin twin.
"""
import functools
import hashlib
import io
import itertools
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import NamedTuple

from . import ConfigMissing, match, ocr, vlm

# ------------------------------------------------------------------------------------------------ the one cleaning

# Letters the readers return for the Latin letters they are drawn as. Every look-alike table the kit kept before is in
# here (camkit.match's CYRILLIC and LOOKALIKES, camkit.safety's guard table, proving.screens' cell letters,
# pass2_report's, writer.labels' and provers.boxes_run's), with a few more marked "added".
_LETTERS = {
    # Cyrillic capitals
    "\u0405": "S",   # CYRILLIC CAPITAL LETTER DZE
    "\u0406": "I",   # CYRILLIC CAPITAL LETTER BYELORUSSIAN-UKRAINIAN I
    "\u0408": "J",   # CYRILLIC CAPITAL LETTER JE
    "\u0410": "A",   # CYRILLIC CAPITAL LETTER A
    "\u0412": "B",   # CYRILLIC CAPITAL LETTER VE
    "\u0415": "E",   # CYRILLIC CAPITAL LETTER IE
    "\u041A": "K",   # CYRILLIC CAPITAL LETTER KA
    "\u041C": "M",   # CYRILLIC CAPITAL LETTER EM
    "\u041D": "H",   # CYRILLIC CAPITAL LETTER EN
    "\u041E": "O",   # CYRILLIC CAPITAL LETTER O
    "\u0420": "P",   # CYRILLIC CAPITAL LETTER ER
    "\u0421": "C",   # CYRILLIC CAPITAL LETTER ES
    "\u0422": "T",   # CYRILLIC CAPITAL LETTER TE
    "\u0423": "Y",   # CYRILLIC CAPITAL LETTER U (added)
    "\u0425": "X",   # CYRILLIC CAPITAL LETTER HA
    "\u04AE": "Y",   # CYRILLIC CAPITAL LETTER STRAIGHT U (added)
    "\u04C0": "I",   # CYRILLIC LETTER PALOCHKA (added)
    "\u051A": "Q",   # CYRILLIC CAPITAL LETTER QA (added)
    "\u051C": "W",   # CYRILLIC CAPITAL LETTER WE (added)
    # Cyrillic small letters (em, te, ve, en and ka drawn as small capitals)
    "\u0430": "a",   # CYRILLIC SMALL LETTER A
    "\u0432": "b",   # CYRILLIC SMALL LETTER VE
    "\u0435": "e",   # CYRILLIC SMALL LETTER IE
    "\u043A": "k",   # CYRILLIC SMALL LETTER KA
    "\u043C": "m",   # CYRILLIC SMALL LETTER EM
    "\u043D": "h",   # CYRILLIC SMALL LETTER EN
    "\u043E": "o",   # CYRILLIC SMALL LETTER O
    "\u0440": "p",   # CYRILLIC SMALL LETTER ER
    "\u0441": "c",   # CYRILLIC SMALL LETTER ES
    "\u0442": "t",   # CYRILLIC SMALL LETTER TE
    "\u0443": "y",   # CYRILLIC SMALL LETTER U
    "\u0445": "x",   # CYRILLIC SMALL LETTER HA
    "\u0455": "s",   # CYRILLIC SMALL LETTER DZE
    "\u0456": "i",   # CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
    "\u0458": "j",   # CYRILLIC SMALL LETTER JE
    "\u04AF": "y",   # CYRILLIC SMALL LETTER STRAIGHT U (added)
    "\u04CF": "l",   # CYRILLIC SMALL LETTER PALOCHKA (added)
    "\u0501": "d",   # CYRILLIC SMALL LETTER KOMI DE
    "\u051B": "q",   # CYRILLIC SMALL LETTER QA
    "\u051D": "w",   # CYRILLIC SMALL LETTER WE
    # Greek capitals
    "\u037F": "J",   # GREEK CAPITAL LETTER YOT (added)
    "\u0391": "A",   # GREEK CAPITAL LETTER ALPHA
    "\u0392": "B",   # GREEK CAPITAL LETTER BETA
    "\u0395": "E",   # GREEK CAPITAL LETTER EPSILON
    "\u0396": "Z",   # GREEK CAPITAL LETTER ZETA
    "\u0397": "H",   # GREEK CAPITAL LETTER ETA
    "\u0399": "I",   # GREEK CAPITAL LETTER IOTA
    "\u039A": "K",   # GREEK CAPITAL LETTER KAPPA
    "\u039C": "M",   # GREEK CAPITAL LETTER MU
    "\u039D": "N",   # GREEK CAPITAL LETTER NU
    "\u039F": "O",   # GREEK CAPITAL LETTER OMICRON
    "\u03A1": "P",   # GREEK CAPITAL LETTER RHO
    "\u03A4": "T",   # GREEK CAPITAL LETTER TAU
    "\u03A5": "Y",   # GREEK CAPITAL LETTER UPSILON
    "\u03A7": "X",   # GREEK CAPITAL LETTER CHI
    # Greek small letters drawn as Latin ones
    "\u03B1": "a",   # GREEK SMALL LETTER ALPHA
    "\u03B9": "i",   # GREEK SMALL LETTER IOTA
    "\u03BA": "k",   # GREEK SMALL LETTER KAPPA
    "\u03BD": "v",   # GREEK SMALL LETTER NU
    "\u03BF": "o",   # GREEK SMALL LETTER OMICRON
    "\u03C1": "p",   # GREEK SMALL LETTER RHO
    "\u03C5": "u",   # GREEK SMALL LETTER UPSILON (added)
    "\u03F3": "j",   # GREEK LETTER YOT (added)
    # Latin letters outside ASCII that no accent explains
    "\u0131": "i",   # LATIN SMALL LETTER DOTLESS I (added)
    "\u0237": "j",   # LATIN SMALL LETTER DOTLESS J (added)
    "\u0261": "g",   # LATIN SMALL LETTER SCRIPT G (added)
}
LETTERS = str.maketrans(_LETTERS)

# Marks the readers write for the camera's own: quotation marks and primes for its seconds mark and apostrophe, the
# angle quotation marks for its breadcrumb's ">" (what page_model.key_text and camkit.match.key mend)
_MARKS = str.maketrans({
    "\u2018": "'",   # LEFT SINGLE QUOTATION MARK
    "\u2019": "'",   # RIGHT SINGLE QUOTATION MARK
    "\u2032": "'",   # PRIME
    "\u201C": '"',   # LEFT DOUBLE QUOTATION MARK
    "\u201D": '"',   # RIGHT DOUBLE QUOTATION MARK
    "\u201E": '"',   # DOUBLE LOW-9 QUOTATION MARK
    "\u2039": "<",   # SINGLE LEFT-POINTING ANGLE QUOTATION MARK
    "\u203A": ">",   # SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
})
# every dash a hyphen (camkit.safety's; pass2_report's scale dashes are among them, and NFKC makes the full-width
# hyphen-minus one): HYPHEN to HORIZONTAL BAR, MINUS SIGN, SMALL EM DASH, SMALL HYPHEN-MINUS
_DASHES = re.compile(r"[\u2010-\u2015\u2212\uFE58\uFE63]")


# Spacing marks the readers write for the camera's apostrophe and seconds mark, mended before NFKC, which would write
# the accent as a space and a combining mark ("Don t") and the double prime as two primes
_SPACING_MARKS = str.maketrans({
    "\u00B4": "'",   # ACUTE ACCENT
    "\u02B9": "'",   # MODIFIER LETTER PRIME
    "\u02BC": "'",   # MODIFIER LETTER APOSTROPHE
    "\u2033": '"',   # DOUBLE PRIME: the seconds mark
})


def canonical(text) -> str:
    """A reading as every comparison takes it: compatibility forms as their plain letters (full-width letters, a
    no-break space, a ligature), accents and other combining marks left out (an i with a circumflex is "i"), and a
    spacing accent with them (never a space inside a word), format characters (zero-width spaces, joiners) left out,
    every dash a hyphen, the quotation marks, primes and the acute accent the readers write as the camera's own '"' and
    "'" (a double prime, and two apostrophes after a number, are its seconds mark '"'), the angle quotation mark as
    ">", Cyrillic and Greek look-alikes as the Latin letters they are drawn as (LETTERS), and each run of spacing one
    space, none at the ends. Case is kept. A letter with no Latin twin (a Cyrillic ZE, a Chinese character) is kept as
    it is: doubts() names it."""
    return _canonical(str(text or ""))


@functools.lru_cache(maxsize=1 << 16)
def _canonical(text: str) -> str:
    t = unicodedata.normalize("NFKD", unicodedata.normalize("NFKC", text.translate(_SPACING_MARKS)))
    kept = [c for i, c in enumerate(t) if unicodedata.category(c) not in ("Mn", "Cf")
            and not (c == " " and unicodedata.category(t[i + 1:i + 2] or "a") == "Mn")]
    t = _DASHES.sub("-", unicodedata.normalize("NFC", "".join(kept))).translate(_MARKS)
    t = re.sub(r"(?<=\d)''", '"', t).translate(LETTERS)
    return re.sub(r"\s+", " ", t).strip()


# Characters read for digits, taken only where digits are compared (a code, a label's runs of digits: PP3 read with a
# Cyrillic ER and a Cyrillic ZE is PP3), never by canonical, which keeps every letter a letter: camkit.safety's
# Picture Profile digits, and the small i (canonical makes a Cyrillic one, read for a 1, Latin).
_DIGITS = {
    "O": "0", "o": "0",
    "\u041E": "0",   # CYRILLIC CAPITAL LETTER O
    "\u043E": "0",   # CYRILLIC SMALL LETTER O
    "\u039F": "0",   # GREEK CAPITAL LETTER OMICRON
    "\u03BF": "0",   # GREEK SMALL LETTER OMICRON
    "l": "1", "I": "1", "i": "1", "|": "1", "!": "1",
    "\u0406": "1",   # CYRILLIC CAPITAL LETTER BYELORUSSIAN-UKRAINIAN I
    "\u0456": "1",   # CYRILLIC SMALL LETTER BYELORUSSIAN-UKRAINIAN I
    "Z": "2", "z": "2",
    "\u0417": "3",   # CYRILLIC CAPITAL LETTER ZE
    "\u0437": "3",   # CYRILLIC SMALL LETTER ZE
    "\u01B7": "3",   # LATIN CAPITAL LETTER EZH
    "\u0292": "3",   # LATIN SMALL LETTER EZH
    "S": "5", "s": "5",
    "\u0405": "5",   # CYRILLIC CAPITAL LETTER DZE
    "\u0455": "5",   # CYRILLIC SMALL LETTER DZE
    "b": "6",
    "\u0431": "6",   # CYRILLIC SMALL LETTER BE
    "B": "8",
    "\u0412": "8",   # CYRILLIC CAPITAL LETTER VE
}
# a sign read for a code's letter: RapidOCR's "(1" for an axis cell's C1 (proving.screens' cell letters)
_CODE_SIGNS = {"(": "C"}
STAR = "\u2605"            # BLACK STAR: the camera's rating stars, counted from pixels, never from a reading


# ------------------------------------------------------------------------------------------------ doubts

EXPECTS = ("label", "number", "code", "button", "text")
PLAIN_MIN = 4              # characters a reading needs to be plain (spacing not counted)
CONF_FLOOR = None          # OCR's confidence below which a reading is doubted: off until the census has calibrated it
# a letter OCR reads for a digit (_DIGITS' Latin ones) right beside a digit or across a decimal point: "PP1O" for
# PP10, "F2.o" for F2.8 (kit/provers/customshoot_values.py, 2026-11-07)
_BESIDE = re.compile(r"\d[.,]?[OoIl|!ZzSsBb]|[OoIl|!ZzSsBb][.,]?\d")
# what canonical writes for a dash, a quotation mark, a prime or an angle quotation mark: a reading so cleaned changed
# no word, and that alone is no doubt
_PUNCTUATION = frozenset("-'\"<>")
_norm = functools.lru_cache(maxsize=1 << 16)(match.norm)


def _cleaned(raw: str) -> list:
    """Each character of a raw reading outside ASCII that the cleaning changes, or keeps though it is a letter or digit
    no English menu draws, once, as (kind, Unicode name):
      lookalike   a letter or digit canonical makes a Latin letter or digit (a Cyrillic ES, an accented e, a
                  full-width F, a superscript two)
      foreign     a letter or digit it does not (a Cyrillic ZE, a German sharp s, a micro sign, a Chinese character)
      cleaned     any other character it changes: a symbol it spells out in letters (a circled M, the numero sign, an
                  ellipsis), a combining mark left on its own, an invisible format character (a zero-width space)
    Spacing, and the dashes, quotation marks and primes it writes as the camera's own, are left out: they change no
    word. The camera's own signs, which it keeps (the stars, the plus-minus sign, the arrows), are no doubt either."""
    out = []
    for c in dict.fromkeys(unicodedata.normalize("NFC", raw)):
        if c.isascii() or c.isspace():
            continue
        clean = canonical(c)
        letter = unicodedata.category(c)[0] in "LN"
        if clean == c:
            if letter:
                out.append(("foreign", unicodedata.name(c, f"U+{ord(c):04X}")))
            continue
        if clean in _PUNCTUATION:
            continue
        kind = ("lookalike" if clean and clean.isascii() and clean.isalnum() else "foreign") if letter else "cleaned"
        out.append((kind, unicodedata.name(c, f"U+{ord(c):04X}")))
    return out


@functools.lru_cache(maxsize=1 << 16)
def _unring(text: str) -> str:
    """A reading without what the screen draws round an option and OCR reads as text, for a label, a number and a code
    alike (camkit.match.clean does this for a label alone): a bullet or ring sign before it, a radio ring read as "o"
    or "O" before it (spaced, or glued to a digit or a sign) or after it, a ring read as a zero and a space before
    anything but a digit or an arrow ("0 +1 EV", "0 (empty)", '0 "Cancel" first'), and a stop or colon at its end;
    canonical first. A zero before an arrow is the camera's own ("0 -> -(minus) -> +(plus)"). A zero glued to a digit,
    or spaced before one, stays: it is a ring or a point lost ("04\"", "0 4\"" for 0.4"), which only the options can
    tell apart (_variants)."""
    t = canonical(text)
    t = re.sub(r"^[\u2022\u00B7\u25E6\u25CF\u25CB]\s*", "", t)
    t = re.sub(r"^[oO]\s+(?=\S)|^[oO](?=[\d+\-\u00B1\u2021])", "", t)
    t = re.sub(r"^0\s+(?![\d\s]|-\s*>|\u2192)", "", t)
    t = re.sub(r"(?<=\S)\s+[oO]$", "", t)
    return re.sub(r"[.:]+$", "", t).strip()


@functools.lru_cache(maxsize=1 << 16)
def number_key(text) -> str:
    """A number as two readings of it are compared: _unring's text, a thin stroke OCR reads for a 1 ("|", "!") a 1
    (never left out: "1/|25" is 1/125, not 1/25), without the plus-minus sign, OCR's double dagger for it, spacing, a
    colon or a comma not between two digits and the ASCII punctuation that is no part of a number (+ - . % / and the
    seconds mark are), so that plus-minus zero, "+-0", "+0", "-0" and "-0.0" are all "0", "+2" is "2" and "80%" is
    "80": the rule pass2_report.scale_key(scale_clean()) gives a scale's number, which keeps no "/", no '"' and no colon
    ("1/250" is not "1250" here, nor "4:3" "43"). A space or a comma between two digits stays, as a point read wrong
    ("F1 1" and "F1,1" are neither F1.1 nor F11). Any other sign stays (an arrow, a star): two labels it tells apart
    are never one number."""
    t = _unring(str(text or "")).translate(_THIN_ONES)
    t = re.sub(r"(?<!\d)\s+|\s+(?!\d)", "", t)
    t = re.sub(r"(?<!\d)[:,]|[:,](?!\d)", "", t)
    t = re.sub(r"[\u00B1\u2021#$&'()*;<=>?@\[\\\]^_`{}~]", "", t)
    t = re.sub(r"^(?:\+-|-\+)(?=0+(?:\.0+)?%?$)", "", t)
    t = t.removesuffix("%").removeprefix("+")
    return "0" if re.fullmatch(r"-?0+(?:\.0+)?", t) else t


def _digit_of(c: str) -> str | None:
    if c.isascii() and c.isdigit():
        return c
    return _DIGITS.get(c) or _DIGITS.get(canonical(c))


# a dot or a colon at an edge, with no letter, digit or thin stroke read for a 1 on one side of it: left out of a code
# and of what a button or a text says ("XL.", "OK.", "Cont. Shooting"); one between two of them stays ("F1.1" is not
# "F11", nor "F1.l" with OCR's l for the 1, nor "F1.|"; 1.3" is not 13", "4:3" is not "43")
_EDGE_POINT = re.compile(r"(?<![^\W_])(?<![|!])[.:]|[.:](?![^\W_])(?![|!])")
# the thin strokes OCR reads for a 1, which no reading may leave out ("F|4" is F14, not F4)
_THIN_ONES = str.maketrans({"|": "1", "!": "1"})
_DECIMAL = "0123456789"


@functools.lru_cache(maxsize=1 << 16)
def _decimal_points(text: str) -> tuple:
    """Each point or colon of a label between two digits (a thin stroke read as the 1 it is drawn as: "F1.|" is F1.1),
    as (how many digits come before it, the sign): part of the label, which camkit.match.norm's key loses for a
    look-alike, so two labels agree only where these are alike ("F1.1" is not F11, "4:3" not 4.3). A point or colon
    beside a letter is no decimal point, a look-alike letter included ("S:12M", "Auto:1", "Del.Select"): readers drop
    or space it, and it tells no option from another. Counted in digits, so neither case nor spacing moves it."""
    t = text.translate(_THIN_ONES)
    out, n = [], 0
    for i, c in enumerate(t):
        if c in _DECIMAL:
            n += 1
        elif c in ".:" and 0 < i < len(t) - 1 and t[i - 1] in _DECIMAL and t[i + 1] in _DECIMAL:
            out.append((n, c))
    return tuple(out)


@functools.lru_cache(maxsize=1 << 16)
def _digit_runs(text: str) -> tuple:
    """The runs of digits a label reads, in order, a thin stroke read as a 1 and anything else ending a run: letters,
    look-alikes among them, are letters here, so case and spacing beside a letter change nothing ("b1" and "B1",
    "10Sec" and "10 Sec"). Two labels name one option only with the same runs: "F1.l" (OCR's l for the 1) is not F11,
    "04\"" and "0 4\"" (a ring, or a point lost) not 4", "F1 1" not F11; camkit.match.norm's key would take each for
    the other."""
    return tuple(re.findall(r"[0-9]+", text.translate(_THIN_ONES)))


# after _unring, a leading I or thin stroke before a digit: camkit.match.norm drops it as the plus-minus sign; here it
# is the plus-minus only before a zero with decimals ("I0.0"), else the 1 it is drawn as ("I5 Sec" is 15 Sec); and a
# sign before a lone zero ("+0 EV", "-0", "+-0", OCR's double dagger) is the plus-minus the camera draws there
_LEAD = re.compile(r"^[I|](?=\d)")
_SIGN_ZERO = re.compile(r"^(?:\+-|-\+|[+\-\u2021\u00B1])\s*(?=0(?:\.0+)?(?![\d.]))")


@functools.lru_cache(maxsize=1 << 16)
def _label_form(text: str) -> str:
    """A label reading as the label rules compare it: _unring's text, a sign before a lone zero the plus-minus sign,
    and a leading I or thin stroke before a digit a 1 ("I5 Sec" is 15 Sec, never 5 Sec; "I20mm" 120mm), or the
    plus-minus sign before a zero with decimals ("I0.0"), which camkit.match.norm then leaves out as it leaves out the
    sign itself. Before a bare zero ("I0", "I0 EV") the I is a 1 here: whether it is the plus-minus sign instead only
    the options can say (_variants)."""
    t = _SIGN_ZERO.sub("\u00B1", _unring(text))
    if _LEAD.match(t):
        t = ("\u00B1" if re.match(r"0\.0+(?![\d.])", t[1:]) else "1") + t[1:]
    # a zero of the camera's own before a space and a sign, glued to it: camkit.match.norm would take it for a ring
    return re.sub(r"^0\s+(?=[^\d\s])", "0", t)


def _label_alike(a: str, b: str) -> bool:
    """Two label forms that may name one option: the same decimal points and the same runs of digits."""
    return _decimal_points(a) == _decimal_points(b) and _digit_runs(a) == _digit_runs(b)


@functools.lru_cache(maxsize=1 << 16)
def _code_chars(text: str) -> tuple:
    t = _EDGE_POINT.sub("", unicodedata.normalize("NFC", _unring(text)))
    t = re.sub(r"(?<!\d)\s+|\s+(?!\d)", "", t)           # a space between two digits stays: a point read wrong
    return tuple(c for c in t if unicodedata.category(c) not in ("Mn", "Cf"))


def code_same(a, b) -> bool:
    """Two readings of one short code ("C3", "PP3", "XL"), each _unring's text, character by character: the same letter
    in any case once canonical, or a digit and a character read for it (_DIGITS: a Cyrillic ZE for the 3 of PP3, "PP1O"
    for PP10), or a sign read for a letter ("(1" for C1). Spacing is left out ("PP 3") but between two digits ("F1 1"
    is not F11), and a dot or colon at an edge ("XL."); one between two letters or digits, or thin strokes read for a
    1, stays ("F1.1" is never F11, nor "F1.l" or "F1.|")."""
    x, y = _code_chars(str(a or "")), _code_chars(str(b or ""))
    if not x or len(x) != len(y):
        return False
    for p, q in zip(x, y, strict=True):
        cp, cq = canonical(p).upper(), canonical(q).upper()
        if cp == cq or _CODE_SIGNS.get(p) == cq or _CODE_SIGNS.get(q) == cp:
            continue
        dp, dq = _digit_of(p), _digit_of(q)
        if dp and dp == dq and (p.isdigit() or q.isdigit()):
            continue
        return False
    return True


@functools.lru_cache(maxsize=1 << 16)
def said_key(text, button: bool = False) -> str:
    """What a button or a text says, as two readings of it are compared: canonical, lower case, without spacing and
    without the punctuation that changes no meaning (commas, brackets, quotation marks, a stop or colon not between
    digits), every other sign kept: "Hi+" is not "Hi", "+0.3" not "-0.3", two stars not one. A button's 0 not beside a
    digit is its O ("0K" is OK)."""
    t = _EDGE_POINT.sub("", canonical(text).lower())
    t = re.sub(r"[\s,;!?()\[\]{}'\"_]", "", t)
    return re.sub(r"(?<!\d)0(?!\d)", "o", t) if button else t


def star_key(text) -> str:
    """A reading holding the camera's rating stars as two readings of it are compared: _unring's text without spacing,
    in lower case. Stars are counted from pixels (pass2_report.name_of), and OCR reads them as "*" or "+": two readings
    with stars name one thing only when this is the same, whatever else they hold."""
    return re.sub(r"\s", "", _unring(str(text or ""))).lower()


def _hits(text, expect: str, choices) -> tuple:
    """(the options the reading names exactly, those it names at all), as indices into choices, by expect's rule. For a
    label, a number or a code, an option holding stars, or any option where the reading holds them, is named only by an
    equal star_key, never by a likeness (agree's star rule)."""
    if expect not in ("button", "text"):
        starred = STAR in canonical(text)
        stars = {i for i, o in enumerate(choices) if starred or STAR in canonical(o)}
        if stars:
            same = [i for i in sorted(stars) if star_key(choices[i]) == star_key(text)]
            rest = [i for i in range(len(choices)) if i not in stars]
            exact, named = _hits(text, expect, tuple(choices[i] for i in rest)) if rest else ([], [])
            return same + [rest[i] for i in exact], same + [rest[i] for i in named]
    if expect == "number":
        k = number_key(text)
        same = [i for i, o in enumerate(choices) if k and number_key(o) == k]
        return same, same
    if expect == "code":
        same = [i for i, o in enumerate(choices) if code_same(text, o)]
        return same, same
    if expect in ("button", "text"):
        k = said_key(text, expect == "button")
        same = [i for i, o in enumerate(choices) if k and said_key(o, expect == "button") == k]
        return same, same
    t, forms = _label_form(text), [_label_form(o) for o in choices]
    kept = [(i, o) for i, o in enumerate(forms) if _label_alike(o, t)]
    exact = [i for i, o in kept if _norm(o) == _norm(t) and match.same(o, t)]
    if exact:
        return exact, exact
    # named at all: loosely (match.same), or with its look-alikes read as the digits they stand for (code_same): a
    # reading that is both another option's loose likeness and this one's look-alike names several, so none
    # ("Shot MarkZ Only": Shot Mark Only loosely, Shot Mark2 Only by its Z)
    alike = [i for i, o in enumerate(forms) if code_same(t, o)]
    return exact, list(dict.fromkeys(alike + [i for i, o in kept if match.same(o, t)]))


@functools.lru_cache(maxsize=1 << 16)
def _variants(text: str) -> tuple:
    """A reading, and what else the same text can be, for the options to decide between (choice_of): a zero and a space
    before a digit is a radio ring or a point read as a space ("0 4\"": 4" or 0.4"); an I or thin stroke before a zero
    with no digit or point after it is a 1 or the plus-minus sign ("I0 EV": 10 EV or the plus-minus zero); an o glued
    after a digit is a ring or a 0 ("1/25o": 1/25 or 1/250); an O or o glued before a capital and "&" or "+" is a ring
    or a letter ("OS&Q Record Setting": S&Q Record Setting with a ring). Where the options hold two of them by exact
    names the reading names neither (an exact name outweighs a loose likeness). Without options such a reading agrees
    with nothing (agree)."""
    u, out = _unring(text), [text]
    m = re.match(r"0\s+(?=\d)", u)
    if m:
        out += [u[m.end():], "0." + u[m.end():]]
    if re.match(r"[I|]0(?![\d.])", u):
        out += ["1" + u[1:], "\u00B1" + u[1:]]
    m = re.search(r"(?<=\d)[oO](?![A-Za-z0-9])", u)
    if m:
        out += [u[:m.start()] + u[m.end():], u[:m.start()] + "0" + u[m.end():]]
    if re.match(r"[oO](?=[A-Z][&+])", u):
        out += [u[1:]]
    return tuple(dict.fromkeys(out))


@functools.lru_cache(maxsize=8192)
def _choice(text: str, expect: str, choices: tuple) -> int | None:
    exact, named = set(), set()
    for v in _variants(text):
        e, n = _hits(v, expect, choices)
        exact.update(e)
        named.update(n)
    hits = exact or named
    return next(iter(hits)) if len(hits) == 1 else None


def choice_of(text, expect: str, choices) -> int | None:
    """The one option of choices the reading names (exactly, else the only one it names at all), or None. Where the
    text can be read two ways (_variants), every way counts: two that name two options name none."""
    return _choice(str(text or ""), expect, tuple(str(o) for o in choices or ()))


def doubts(text, expect: str, *, lines=(), choices=(), lit: bool = False) -> list:
    """Why OCR's reading `text` of something of the kind `expect` ("label", "number", "code", "button", "text") is not
    plain enough to be trusted alone, as short reasons whose words before ":" are the kind (the census counts by it);
    [] for a plain reading. Pure: no I/O. lines: the ocr.Line list the reading was made of (their confidence, once
    CONF_FLOOR is set); choices: the options expected there (no option, several, loose are judged only with them);
    lit: something is lit there, so an empty reading is a doubt ("empty"), where an empty reading of a place with
    nothing lit is none.
      lookalike: <NAME>    a letter or digit outside ASCII that canonical makes Latin (a Cyrillic ES in "C.Temp")
      foreign: <NAME>      one it does not (a Cyrillic ZE read for a 3, a German sharp s, a Chinese character)
      cleaned: <NAME>      any other character the cleaning changes (a circled M, the numero sign, a combining mark on
                           its own, a zero-width space); dashes, quotation marks and spacing apart (_cleaned)
      short: <n>           a number or code (a digit in it, or expect "number" or "code") of 3 characters or fewer
      short word: <n>      a word that short ("Off", "Lo"), counted apart so that the census shows what it costs
      letter by digit: <s> a digit's look-alike letter beside a digit ("PP1O", "F2.o"), unless the one option the
                           reading names exactly is written so
      no number            expect "number" and no digit read
      no option            with choices: names none of them
      several options: <n> names more than one
      loose                names one only loosely (camkit.match.same, not the same key)
      low confidence: <c>  an OCR line below CONF_FLOOR (never while CONF_FLOOR is None)"""
    if expect not in EXPECTS:
        raise ValueError(f"expect {expect!r}: one of {', '.join(EXPECTS)}")
    raw = str(text or "")
    canon = canonical(raw)
    if not canon:
        return ["empty"] if lit else []
    out = [f"{kind}: {name}" for kind, name in _cleaned(raw)]
    core = re.sub(r"\s", "", canon)
    digit = bool(re.search(r"\d", core))
    if expect == "number" and not digit:
        out.append("no number")
    if len(core) < PLAIN_MIN and expect != "text":
        out.append(f"short: {len(core)}" if digit or expect in ("number", "code") else f"short word: {len(core)}")
    choices = list(choices or ())
    judged = bool(choices) and expect != "text"
    exact, named = _hits(canon, expect, choices) if judged else ([], [])
    beside = list(dict.fromkeys(_BESIDE.findall(canon)))
    if len(exact) == 1:
        written = canonical(choices[exact[0]])
        beside = [s for s in beside if s not in written]
    out += [f"letter by digit: {s}" for s in beside]
    if judged:
        if len(exact) > 1 or (not exact and len(named) > 1):
            out.append(f"several options: {len(exact) if len(exact) > 1 else len(named)}")
        elif not exact:
            out.append("loose" if named else "no option")
    if CONF_FLOOR is not None and lines:
        low = min(float(getattr(ln, "conf", 1.0)) for ln in lines)
        if low < CONF_FLOOR:
            out.append(f"low confidence: {low:.2f}")
    return out


def kind_of(reason: str) -> str:
    """A doubt's kind: its words before ":" ("lookalike: CYRILLIC SMALL LETTER ER" is "lookalike")."""
    return reason.split(":", 1)[0]


def agree(a, b, expect: str, choices=()) -> bool:
    """Whether two readings (two eyes', or a reading and a label) name the same thing, by the kind of thing expected,
    each canonical first. An empty reading agrees with nothing. With choices (the options expected there), whatever the
    kind, both must name the same one option (choice_of). Without:
      label    each read as _label_form reads it (a leading I or thin stroke before a digit a 1), then the same key
               (camkit.match.norm: case, spacing, stops and OCR's l/1, O/0 aside), the same runs of digits and decimal
               points (_digit_runs, _decimal_points: "F1.l" is not F11, "04\"" not 4") and match.same's word rules
               ("Lo" is not "10"); never match.same's loose likeness alone, which takes "Registered" for "Not
               registered". A point lost whole ("F11" read for F1.1) is the other label's own text: no rule on the
               text can tell it
      number   number_key alike ("+2" and "2", a minus sign and a hyphen, plus-minus zero and "0"; "1/4000" is not
               "1/400")
      code     code_same (PP3 with a Cyrillic ZE, and PP3; "F1.1" is never F11)
      button   said_key alike, a 0 read for an O ("0K" is OK); a sign or a star more or less is another button
      text     said_key alike
    A label, number or code with rating stars agrees only when both read it alike but for spacing and case, whatever
    the choices: stars are counted from pixels (pass2_report.name_of), and OCR reads them as "*" or "+"."""
    if expect not in EXPECTS:
        raise ValueError(f"expect {expect!r}: one of {', '.join(EXPECTS)}")
    ca, cb = canonical(a), canonical(b)
    if not ca or not cb:
        return False
    if expect not in ("button", "text") and STAR in ca + cb:
        return star_key(ca) == star_key(cb)
    choices = tuple(str(o) for o in choices or ())
    if choices:
        i = choice_of(ca, expect, choices)
        return i is not None and i == choice_of(cb, expect, choices)
    if expect in ("button", "text"):
        k = said_key(ca, expect == "button")
        return bool(k) and k == said_key(cb, expect == "button")
    if len(_variants(ca)) > 1 or len(_variants(cb)) > 1:
        return False                    # two ways to read it, and no options to choose between them (_variants)
    if expect == "number":
        return bool(number_key(ca)) and number_key(ca) == number_key(cb)
    if expect == "code":
        return code_same(ca, cb)
    fa, fb = _label_form(ca), _label_form(cb)
    return _norm(fa) == _norm(fb) and _label_alike(fa, fb) and match.same(fa, fb)


# ------------------------------------------------------------------------------------------------ the votes

@dataclass(frozen=True)
class Vote:
    """One eye's reading of a place. eye: "ocr" (the OCR engine configured), "ocr2" (the second OCR engine, where one
    is installed), "reader" (the "second" reader), "third" (the "third" reader, of another model), "check" (a site's
    own check that is no reader); source: what read it, "ocr:<engine>", "reader:<model>" or "check:site"; text: as read
    (None: asked, and no answer); frame: the file name of the frame it was read on."""
    eye: str
    source: str
    text: str | None
    frame: str | None = None


def tally(votes, expect: str, choices=()) -> tuple:
    """(a Vote whose reading stands, the eyes behind it), or (None, ()): a reading stands when votes from two or more
    independent sources name it and no reading that names something else has as many. A source votes once: two readers
    of one model, or one reader asked twice, are one vote. Votes stand together only as a group whose every two members
    agree (agree, with the same choices: the one predicate, so a reading tally keeps is one agree takes); agree is not
    transitive for codes ("PPB" agrees with "PP8" and "PPb", which do not agree), so a reading two contradicting votes
    each lean to stands for neither. With choices a vote that names none of them backs nothing."""
    choices = tuple(str(o) for o in choices or ())
    said = [v for v in votes if v.text and canonical(v.text)]
    if choices:
        said = [v for v in said if choice_of(v.text, expect, choices) is not None]
    groups = {}
    for i, v in enumerate(said):
        # agree itself decides who stands together, so a reading tally keeps is one agree takes
        members = [j for j, w in enumerate(said) if j == i or agree(v.text, w.text, expect, choices)]
        if all(agree(said[a].text, said[b].text, expect, choices) for a, b in itertools.combinations(members, 2)):
            groups.setdefault(tuple(members), [said[j] for j in members])
    ranked = sorted(groups.values(), key=lambda g: len({w.source for w in g}), reverse=True)
    if not ranked:
        return None, ()
    n = len({w.source for w in ranked[0]})
    if n < 2 or (len(ranked) > 1 and len({w.source for w in ranked[1]}) == n):
        return None, ()
    return ranked[0][0], tuple(w.eye for w in ranked[0])


OUTCOMES = ("plain", "stands on both", "stands on one reader", "one reader, no options", "ocr names no option",
            "readers apart", "reader needed")
APART = ("ocr names no option", "readers apart")       # a fresh frame, then the third vote, then refused


def outcome(ocr_text, said, expect: str, choices=(), ds=None) -> str:
    """What the first two votes, OCR's reading and the reader's (None: no answer), make of a reading, pure (the third
    vote is read()'s, after a fresh frame):
      plain                   no doubt: OCR alone stands
      stands on both          the reader and the cleaned OCR name the same thing
      stands on one reader    OCR read nothing, and the reader names exactly one expected option: one reader's
                              reading, never alone for a press or a guard
      one reader, no options  OCR read nothing, and no options were given to check the reader's reading against:
                              never stands alone
      ocr names no option     OCR read something that names no option, and the reader names one: as apart (measured
                              on the first camera's proofs, the reader's option was then sometimes another one)
      readers apart           they name two different things, or neither names an option
      reader needed           a doubt, and no answer
    ds: doubts() of ocr_text, when the caller has them. read() decides by it, and so does kit/tools/reader_census.py."""
    choices = tuple(str(o) for o in choices or ())
    if ds is None:
        ds = doubts(ocr_text, expect, choices=choices, lit=True)
    if not ds:
        return "plain"
    if not str(said or "").strip():
        return "reader needed"
    canon = canonical(ocr_text)
    if canon and agree(canon, said, expect, choices):
        return "stands on both"
    if not canon:
        if not choices:
            return "one reader, no options"
        return "stands on one reader" if choice_of(said, expect, choices) is not None else "readers apart"
    if choices and choice_of(canon, expect, choices) is None and choice_of(said, expect, choices) is not None:
        return "ocr names no option"
    return "readers apart"


# ------------------------------------------------------------------------------------------------ the regions read

def _text(name: str):
    def pick(answer: dict):
        v = answer.get(name)
        if isinstance(v, list):
            v = " ".join(str(x) for x in v if x is not None)
        return None if v is None else str(v)
    return pick


def _nth(name: str, k: int):
    def pick(answer: dict):
        v = answer.get(name)
        return str(v[k]) if isinstance(v, list) and 0 <= k < len(v) and v[k] is not None else None
    return pick


def _highlighted(answer: dict):
    """The label of the one menu row the reader marks as the one with the orange bar (camkit.live.reader_label's)."""
    rows = answer.get("rows")
    lit = [r for r in rows or [] if isinstance(r, dict) and r.get("highlighted") is True]
    return str(lit[0].get("label") or "") if len(lit) == 1 else None


@dataclass(frozen=True)
class Region:
    """A place on the screen and the question the reader is asked about it. box: (x0, y0, x1, y1) in the 640 x 480
    frame, or None for the lit item, found on the frame (camkit.live.lit_found). prompt: a camkit.vlm.PROMPTS key, the
    questions the kit asks today, so that the answers already cached are used. pick: the reading in the answer."""
    name: str
    box: tuple | None
    prompt: str
    pick: object = field(compare=False)


LIT = Region("lit", None, "option", _text("selected"))             # the item under the cursor (vlm_option's question)
LIT_ROW = Region("lit row", None, "menu", _highlighted)           # a menu page's lit row (live.reader_label's)
TITLE = Region("title", (0, 0, 640, 52), "option", _text("title"))
CAROUSEL = Region("carousel", (110, 60, 636, 112), "option", _text("selected"))   # a carousel's orange line
FOOTER = Region("footer", (0, 425, 640, 480), "dialog", _text("footer"))
NOTICE = Region("notice", (0, 0, 640, 480), "notice", _text("text"))


def FIELD(k: int, box: tuple) -> Region:
    """A number-entry screen's k-th box (counted from the left), at box."""
    return Region(f"field {k}", tuple(box), "fields", _nth("fields", k))


def BOX(x0: int, y0: int, x1: int, y1: int, prompt: str = "option", pick: str = "selected") -> Region:
    """Any other place, with the question to ask there and the answer's field to read."""
    return Region(f"box {x0},{y0},{x1},{y1}", (x0, y0, x1, y1), prompt, _text(pick))


# ------------------------------------------------------------------------------------------------ the eyes

STAKES = ("guard", "press", "proof", "find", "note")
TIMEOUTS = {"guard": 25.0, "press": 25.0, "proof": 25.0, "find": 15.0}   # s the reader gets, by what rides on it
DOWN_AFTER, DOWN_FOR = 2, 300.0          # failures in a row, then seconds a reader counts as unreachable

_MEMO: dict = {}                         # (role, the frame's SHA-1, the question) -> (answer, name, model)
_DOWN: dict = {}                         # role -> {"fails": n, "until": time.monotonic() it counts as down until}


class Asked(NamedTuple):
    """A reader's answer about a frame (ask): the answer or None, the configured name and model of the reader that
    gave it (a stand-in's included), and why there is no answer ("" when there is)."""
    answer: dict | None
    name: str | None
    model: str | None
    why: str


def forget() -> None:
    """The memo and the latches cleared (a new run in the same process; the tests)."""
    _MEMO.clear()
    _DOWN.clear()


def _ocr_lines(frame, eng: str | None = None) -> list:
    """The OCR seam: the frame's lines from camkit.ocr.read (the configured engine, or eng)."""
    return ocr.read([frame.path], eng=eng)[frame.path]


def _reader_answer(image: bytes, question: str, timeout: float, role: str = "second") -> tuple:
    """The reader seam: (answer, name, model) from the reader playing role ("second", or "third": a reader of another
    model, the tie-breaker), through camkit.vlm.ask_role, a stand-in taking the role when that reader will not
    connect."""
    answer = vlm.ask_role(role, image, question, timeout)
    try:
        cfg = vlm.playing(role)
    except Exception:            # noqa: BLE001 - the name and model are evidence only; the answer stands without them
        cfg = {}
    return answer, cfg.get("name"), cfg.get("model")


def _reader_model(role: str) -> str | None:
    """The model of the reader playing role, or None when private/config.json gives the role no reader (one reader
    listed has no "third")."""
    try:
        cfg = vlm.playing(role)
    except Exception:            # noqa: BLE001 - no reader for the role: NoReader, or a role naming none
        return None
    return cfg.get("model") or cfg.get("name")


def frame_bytes(frame) -> bytes:
    """The frame as the reader is sent it: its saved file, else its picture as a PNG."""
    path = getattr(frame, "path", None)
    if path is not None:
        try:
            return path.read_bytes()
        except OSError:
            pass
    from PIL import Image
    buf = io.BytesIO()
    Image.fromarray(frame.image).save(buf, format="PNG")
    return buf.getvalue()


def reader_down(role: str = "second") -> bool:
    """The latch: the reader playing role failed DOWN_AFTER times in a row less than DOWN_FOR seconds ago."""
    return time.monotonic() < _DOWN.get(role, {}).get("until", 0.0)


def ask(frame, prompt: str, timeout: float = 25.0, role: str = "second") -> Asked:
    """The answer of the reader playing role to camkit.vlm.PROMPTS[prompt] about frame (Asked). Never asked about a
    black frame (camkit.live.black: the readers invent answers on one); asked once per role, frame and question in a
    process (camkit.vlm's own cache keeps the answers on disk); not asked while its latch is down (reader_down). A
    failure, a missing reader (camkit.vlm.NoReader) and an answer that is no JSON object are no answer; the failures
    count towards the latch. A prompt that is no PROMPTS key raises KeyError, before anything is asked."""
    from . import live
    question = vlm.PROMPTS[prompt]
    if live.black(frame):
        return Asked(None, None, None, "a black frame: the reader is never asked about one")
    image = frame_bytes(frame)
    key = (role, hashlib.sha1(image).hexdigest(), prompt)
    if key in _MEMO:
        return Asked(*_MEMO[key], "")
    if reader_down(role):
        return Asked(None, None, None, "the reader did not answer just before (asked again after a pause)")
    down = _DOWN.setdefault(role, {"fails": 0, "until": 0.0})
    try:
        answer, name, model = _reader_answer(image, question, timeout, role)
    except Exception as e:       # noqa: BLE001 - any failure is no answer here; the latch counts it
        down["fails"] += 1
        if down["fails"] >= DOWN_AFTER:
            down["until"] = time.monotonic() + DOWN_FOR
        return Asked(None, None, None, vlm.scrub(f"the reader failed ({type(e).__name__}: {e})"[:300]))
    down.update(fails=0, until=0.0)
    if not isinstance(answer, dict) or "_unparsed" in answer:
        return Asked(None, name, model, "the reader's answer was no JSON object")
    _MEMO[key] = (answer, name, model)
    return Asked(answer, name, model, "")


# ------------------------------------------------------------------------------------------------ one reading

DISAGREE = "the readers name two different things"
ENGINES = ("apple", "rapidocr")          # the OCR engines camkit.ocr.read runs, by the names it runs them by


def engine_of(name) -> str:
    """The OCR engine camkit.ocr.read runs for an engine name: "apple" or "rapidocr", the only two names it knows.
    Any other name is refused (ValueError): ocr.read would run Apple Vision for it while camkit.ocr.second() took it
    for another engine than "apple", and one engine would vote twice. Votes are told apart by these names."""
    if name in ENGINES:
        return name
    raise ValueError(f"OCR engine {name!r} (CAMSET_OCR or private/config.json \"ocr\"): the kit knows only "
                     f"{' and '.join(repr(e) for e in ENGINES)}; any other name runs Apple Vision under another name, "
                     f"and a vote would be counted twice")


def check_engines() -> tuple:
    """(the first OCR engine, the second or None) as camkit.ocr.read runs them, checked at every camera run's start by
    camkit.vlm.check_readers, before its readers are asked: an engine name it does not know stops the run there, with
    what to put instead (ConfigMissing, a SystemExit), before anything is pressed."""
    try:
        first = engine_of(ocr.engine())
        other = ocr.second()
        other = engine_of(other) if other else None
    except ValueError as e:
        raise ConfigMissing(str(e)) from None
    return first, (None if other == first else other)


def model_id(model) -> str:
    """A reader's model as votes are told apart by it: its configured id, trimmed and case-folded. Two ids for the same
    weights (an alias, a path and a name) cannot be told apart here and count as two models."""
    return str(model or "unknown").strip().casefold()


@dataclass
class Reading:
    """One reading by the rule. text: canonical, the reader's where OCR was doubted; choice: the index into the options
    expected, None when refused or when it names none; by: "both", "ocr", "reader", "votes" (two or more independent
    votes, tally) or "none"; raw: {"ocr", "ocr2", "reader", and "second" and "third" once asked} as read on the last
    frame (None: not asked, or no answer); doubts: doubts() of OCR's reading on the last frame, with "apart before"
    where an earlier frame was read apart; reader: the configured name of the reader that answered (a stand-in's
    included); refused: "" or why the reading cannot be trusted at its stakes; frame: the last frame's file name;
    votes: every Vote cast, on every frame read, in order; agreed: the eyes whose vote on the last frame names text
    (none when refused)."""
    text: str
    choice: int | None
    by: str
    raw: dict
    doubts: list
    reader: str | None
    refused: str
    frame: str | None
    votes: list = field(default_factory=list)
    agreed: list = field(default_factory=list)

    def independent(self) -> int:
        """How many independent votes stand behind text: the last frame's agreeing ones, one per source (two readers
        of one model are one vote)."""
        return len({v.source for v in self.votes if v.frame == self.frame and v.eye in self.agreed})

    def evidence(self) -> dict:
        """What a proof line carries of this reading ("eyes"): which eyes voted on which frame, with what, and which
        agreed."""
        out = {"by": self.by, "ocr": self.raw.get("ocr"), "reader": self.raw.get("reader")}
        for k in ("ocr2", "second", "third"):
            if self.raw.get(k) is not None:
                out[k] = self.raw[k]
        if self.reader:
            out["reader_name"] = self.reader
        out["votes"] = [{"eye": v.eye, "source": v.source, "text": v.text, "frame": v.frame} for v in self.votes]
        out["agreed"] = list(self.agreed)
        if self.doubts:
            out["doubts"] = list(self.doubts)
        if self.refused:
            out["refused"] = self.refused
        return out

    def texts(self) -> list:
        """Every reading a guard judges: each eye's on every frame read, as read, and canonical beside it, never
        canonical alone (a cleaning can hide a slip a guard would see in the raw reading); each once. Any one refusing
        refuses."""
        got = [v.text for v in self.votes if v.eye in ("ocr", "ocr2", "reader", "third")]
        return list(dict.fromkeys(t for s in got if s for t in (s, canonical(s)) if t))


def _region_box(frame, where: Region, lines: list) -> tuple:
    """(the OCR box, whether something is lit there): the region's own box, else the lit item's (camkit.live), widened
    to every OCR line it touches when it is drawn without a bar (live.line_box); (None, False) when nothing is lit."""
    if where.box is not None:
        return where.box, True
    from . import live
    box, bar = live.lit_found(frame.image)
    if box is None:
        return None, False
    return (box if bar else live.line_box(box, lines)), True


def _picked(where: Region, answer) -> str | None:
    said = where.pick(answer) if isinstance(answer, dict) else None
    return said.strip() if isinstance(said, str) and said.strip() else None


def _second(second, frame):
    got = second(frame) if callable(second) else second
    return str(got).strip() if got is not None and str(got).strip() else None


def _once(frame, where: Region, expect: str, stakes: str, choices: tuple, second, last: bool,
          apart_before: bool) -> Reading:
    name = getattr(getattr(frame, "path", None), "name", None)
    first = engine_of(ocr.engine())
    other = ocr.second()
    other = engine_of(other) if other else None
    other = None if other == first else other            # one engine is one vote, whatever names it goes by
    every = _ocr_lines(frame)
    box, lit = _region_box(frame, where, every)
    raw = {"ocr": None, "ocr2": None, "reader": None}
    if box is None:
        return Reading("", None, "none", raw, [], None, "nothing is lit", name)
    lines = [ln for ln in every if ln.inside(box)]
    said_ocr = " ".join(ln.text for ln in lines).strip()
    raw["ocr"] = said_ocr
    votes = [Vote("ocr", f"ocr:{first}", said_ocr, name)]

    def read_ocr2():
        if other and not any(v.eye == "ocr2" for v in votes):
            raw["ocr2"] = " ".join(ln.text for ln in _ocr_lines(frame, other) if ln.inside(box)).strip()
            votes.append(Vote("ocr2", f"ocr:{other}", raw["ocr2"], name))

    if stakes == "guard":
        read_ocr2()
    ds = doubts(said_ocr, expect, lines=lines, choices=choices, lit=lit)
    if apart_before:
        ds = [*ds, "apart before"]       # once the readers were apart, a plain OCR reading on a later frame is a vote
    asking = stakes in ("press", "proof") or (stakes in ("guard", "find") and bool(ds or not said_ocr))
    asked = ask(frame, where.prompt, TIMEOUTS[stakes]) if asking else Asked(None, None, None, "not asked")
    said = _picked(where, asked.answer)
    why = asked.why or ("the reader's answer names nothing there" if said is None else "")
    raw["reader"] = said
    if asking:
        votes.append(Vote("reader", f"reader:{model_id(asked.model or asked.name)}", said, name))
    canon = canonical(said_ocr)

    def third_reader():
        """A reader of another model than any that voted (the "third" role), when one is configured."""
        model = _reader_model("third")
        if model is None or f"reader:{model_id(model)}" in {v.source for v in votes}:
            return
        got = ask(frame, where.prompt, TIMEOUTS[stakes], role="third")
        raw["third"] = _picked(where, got.answer)
        votes.append(Vote("third", f"reader:{model_id(got.model or model)}", raw["third"], name))

    def check():
        """The site's own check, one more vote: independent of this frame's OCR text and of the readers."""
        backed = _second(second, frame)
        if backed is not None and not any(v.eye == "check" for v in votes):
            raw["second"] = backed
            votes.append(Vote("check", "check:site", backed, name))

    def third_vote():
        """The votes asked after OCR and the reader, one after another until two independent votes name one
        option: the second OCR engine, the site's check, then a reader of another model."""
        for more in (read_ocr2, check, third_reader):
            if tally(votes, expect, choices)[0] is not None:
                return
            more()

    def settled():
        win, _ = tally(votes, expect, choices)
        return None if win is None else canonical(win.text)

    def apart():
        return f"{DISAGREE}: " + ", ".join(f"{v.eye} {v.text!r}" for v in votes if v.text)

    def at_odds() -> bool:
        said_by = [v for v in votes if v.text]
        return any(not agree(x.text, y.text, expect, choices) for x, y in itertools.combinations(said_by, 2))

    def out(text, by, refused=""):
        c = None if refused or not choices else choice_of(text, expect, choices)
        agreed = [] if refused else [v.eye for v in votes if v.text and text and agree(v.text, text, expect, choices)]
        return Reading(text, c, by, raw, ds, asked.name, refused, name, list(votes), agreed)

    if stakes == "guard":
        # guards may only add refusals: any two eyes that read differently refuse, and no vote settles them
        if not (said_ocr or raw["ocr2"] or said):
            return out("", "none", "nothing could be read there: a guard cannot judge it")
        if at_odds():
            return out(canon, "none", apart())
        if ds and said is None:
            return out(canon or canonical(raw["ocr2"]), "ocr" if canon else "none",
                       f"reader needed: {'; '.join(ds)} ({why})")
        if canon:
            return out(canon, "both" if said else "ocr")
        if (text := settled()) is None:                   # OCR read nothing: the reader needs a second vote
            check()
            if (text := settled()) is None:
                third_reader()
                text = settled()
        if at_odds():
            return out(canonical(said), "none", apart())
        if text is None:
            return out(canonical(said), "reader", "one reader's reading never clears a guard alone")
        return out(text, "votes")
    how = outcome(said_ocr, said, expect, choices, ds)
    if how == "plain":
        return out(canon, "both" if said and agree(canon, said, expect, choices) else "ocr")
    if how == "stands on both":
        return out(canonical(said), "both")
    if how == "stands on one reader" and stakes != "press" and not apart_before:
        return out(canonical(said), "reader")
    if how in ("stands on one reader", "one reader, no options"):
        third_vote()
        if (text := settled()) is not None:
            return out(text, "votes")
        why_alone = ("one reader's reading, with no options to check it against" if how == "one reader, no options"
                     else "the readers were apart on an earlier frame: one reader's reading never settles that alone"
                     if apart_before else "one reader's reading never decides a press alone")
        return out(canonical(said), "reader", why_alone)
    if how in APART:
        if last:
            third_vote()
            if (text := settled()) is not None:
                return out(text, "votes")
        return out(canon, "none", apart())
    if stakes == "note":
        return out(canon, "ocr" if canon else "none")
    return out(canon, "ocr" if canon else "none", f"reader needed: {'; '.join(ds)} ({why})")


def read(frame, where: Region, expect: str, stakes: str, *, choices=None, fresh: int = 0, second=None) -> Reading:
    """One reading of the region `where` of a frame, by the rule (the module docstring): OCR's reading, cleaned and
    judged (doubts); the reader asked on a doubt, or always where a press or a proof rides on it; on a disagreement a
    fresh frame, then a third vote; what stands, with every vote cast on every frame (Reading.votes, Reading.agreed).
      frame    a camkit.frames.Frame (its picture and its saved file), or a function that grabs one: with a function,
               a disagreement is read again on up to `fresh` frames grabbed afresh, where a plain OCR reading is a vote
               like the others (never a way out of the disagreement), and the third vote is asked only on the last of
               them; with a frame, on that frame
      where    a Region: LIT, LIT_ROW, TITLE, CAROUSEL, FOOTER, NOTICE, FIELD(k, box) or BOX(x0, y0, x1, y1)
      expect   what is read there: "label", "number", "code", "button" or "text" (doubts, agree)
      stakes   what rides on it, which decides when the reader is asked and what may stand:
                 guard   the second OCR engine reads too, the reader on a doubt or an empty reading; never read again on
                         a fresh frame for a better answer. Refused when no eye reads anything, when any two eyes'
                         readings disagree (no vote settles a guard), on a doubt the reader does not answer, and on a
                         lone reader's reading that no second, independent vote names too (the second OCR engine, the
                         site's check, then a reader of another model, asked only then). Every eye's reading on every
                         frame is kept for the guard to judge (Reading.texts)
                 press   the reader always; a lone reader's reading stands only with a second, independent vote
                 proof   the reader always; a lone reader's reading where OCR read nothing stands, said so in by
                 find    the reader on a doubt only, before any fuzzy fallback of the caller's
                 note    OCR alone, cleaned, never the reader; refused only where nothing is lit
      choices  the options expected there (their labels), one of which the reading names (Reading.choice)
      second   a check of the site's own, one more vote where the readers are apart or one reader stands alone: a
               reading, or a function of the frame giving one. It must be independent of this frame's OCR text and of
               the readers: the marker's place on a Creative Look scale, a count of presses from a known start, pass-1
               pictures of the option; a check worked out from the same OCR text is no second source. It never stands
               in for the reader: with no reader's answer a doubtful reading is refused ("reader needed").
    What it raises, for a caller to handle: ValueError for stakes or expect it does not know, and for an OCR engine
    name camkit.ocr.read does not know (engine_of, on every frame; check_engines finds one at a run's start, before
    anything is pressed); KeyError for a Region whose prompt is no camkit.vlm.PROMPTS key; and whatever camkit.ocr.read
    raises passes through (RuntimeError when the OCR helper cannot read a frame, ImportError when RapidOCR is not
    installed). A reader's failures never raise: they are no answer (ask).
    Nothing calls this yet (2026-11-13): the callers move onto it site by site, once kit/tools/reader_census.py has
    measured what that changes."""
    if stakes not in STAKES:
        raise ValueError(f"stakes {stakes!r}: one of {', '.join(STAKES)}")
    if expect not in EXPECTS:
        raise ValueError(f"expect {expect!r}: one of {', '.join(EXPECTS)}")
    grab = frame if callable(frame) else None
    options = tuple(str(o) for o in choices or ())
    left = fresh if grab and stakes != "guard" else 0
    f = grab() if grab else frame
    votes, apart_before = [], False
    while True:
        got = _once(f, where, expect, stakes, options, second, last=left == 0, apart_before=apart_before)
        votes += got.votes
        if left == 0 or not got.refused.startswith(DISAGREE):
            got.votes = votes
            return got
        apart_before = True
        left -= 1
        f = grab()
