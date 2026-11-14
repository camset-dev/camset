"""camkit.reading, the one rule for when OCR alone is trusted and when the reader is asked (docs/decisions/0022): the
one cleaning (canonical) and, table by table, where it differs from each look-alike table the kit kept before; the
doubts and the agreement by kind; read() through the eyes fixture; kit/tools/reader_census.py; and the modules that
still read the screen by themselves, a list that only gets shorter.

Letters outside ASCII are written as escapes with their Unicode names beside them, so that no reader of this file
takes one for its Latin twin."""
import itertools
import json
import re
import sys
import unicodedata
import urllib.error
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from camkit import ROOT, match, reading, safety  # noqa: E402
from camkit.reading import CAROUSEL, agree, canonical, code_same, doubts, number_key  # noqa: E402

CYR_ES_CAP = "\u0421"        # CYRILLIC CAPITAL LETTER ES
CYR_ER_CAP = "\u0420"        # CYRILLIC CAPITAL LETTER ER
CYR_ER = "\u0440"            # CYRILLIC SMALL LETTER ER
CYR_ZE_CAP = "\u0417"        # CYRILLIC CAPITAL LETTER ZE
CYR_ZE = "\u0437"            # CYRILLIC SMALL LETTER ZE
CYR_EM = "\u043C"            # CYRILLIC SMALL LETTER EM
CYR_O_CAP = "\u041E"         # CYRILLIC CAPITAL LETTER O
CYR_O = "\u043E"             # CYRILLIC SMALL LETTER O
CYR_KA_CAP = "\u041A"        # CYRILLIC CAPITAL LETTER KA
CYR_HA_CAP = "\u0425"        # CYRILLIC CAPITAL LETTER HA
CYR_U_CAP = "\u0423"         # CYRILLIC CAPITAL LETTER U
GREEK_IOTA_CAP = "\u0399"    # GREEK CAPITAL LETTER IOTA
I_CIRCUMFLEX = "\u00EE"      # LATIN SMALL LETTER I WITH CIRCUMFLEX
SHARP_S = "\u00DF"           # LATIN SMALL LETTER SHARP S
CJK = "\u4E2D"              # CJK UNIFIED IDEOGRAPH-4E2D
NB_HYPHEN = "\u2011"         # NON-BREAKING HYPHEN
EN_DASH = "\u2013"           # EN DASH
MINUS = "\u2212"             # MINUS SIGN
FULLWIDTH_HYPHEN = "\uFF0D"  # FULLWIDTH HYPHEN-MINUS
FULLWIDTH_FORMAT = "\uFF26\uFF2F\uFF32\uFF2D\uFF21\uFF34"   # FULLWIDTH LATIN CAPITAL LETTERS F O R M A T
FULLWIDTH_TWO = "\uFF12"     # FULLWIDTH DIGIT TWO
ZWSP = "\u200B"              # ZERO WIDTH SPACE
NBSP = chr(0xA0)        # NO-BREAK SPACE
DOUBLE_PRIME = "\u2033"      # DOUBLE PRIME
RDQUO = "\u201D"             # RIGHT DOUBLE QUOTATION MARK
RSQUO = "\u2019"             # RIGHT SINGLE QUOTATION MARK
RSAQUO = "\u203A"            # SINGLE RIGHT-POINTING ANGLE QUOTATION MARK
RARROW = "\u2192"            # RIGHTWARDS ARROW
PLUS_MINUS = "\u00B1"        # PLUS-MINUS SIGN
DOUBLE_DAGGER = "\u2021"     # DOUBLE DAGGER (OCR's plus-minus)
STAR = "\u2605"              # BLACK STAR
CIRCLED_ONE = "\u2460"       # CIRCLED DIGIT ONE
CIRCLED_M = chr(0x24C2)      # CIRCLED LATIN CAPITAL LETTER M
CYR_IE = chr(0x0435)         # CYRILLIC SMALL LETTER IE
NUMERO = chr(0x2116)         # NUMERO SIGN
COMBINING_TILDE = chr(0x0303)   # COMBINING TILDE
ACUTE = chr(0x00B4)          # ACUTE ACCENT (a spacing accent)
DIAERESIS = chr(0x00A8)      # DIAERESIS (a spacing accent)
LR_ARROW = chr(0x2194)       # LEFT RIGHT ARROW
UD_ARROW = chr(0x2195)       # UP DOWN ARROW


# ---------------------------------------------------------------------------------------------- the one cleaning

CLEANED = [
    (f"{CYR_ES_CAP}.Temp./Filter", "C.Temp./Filter"),
    (f"120{CYR_ER}", "120p"),
    (f"21{CYR_EM} M", "21m M"),
    (f"  Wi{NB_HYPHEN}Fi{NBSP} Direct ", "Wi-Fi Direct"),
    (FULLWIDTH_FORMAT, "FORMAT"),
    (f"For{ZWSP}mat", "Format"),
    (f"2{DOUBLE_PRIME}", '2"'), ("2''", '2"'), (f"2{RDQUO}", '2"'), ("It''s", "It''s"),   # '' after a number only
    (f"Don{ACUTE}t show", "Don't show"), (f"Don{DIAERESIS}t", "Dont"),          # a spacing accent: never a space
    (f"Shooting {RSAQUO} Menu", "Shooting > Menu"), (f"Don{RSQUO}t show", "Don't show"),
    (f"{I_CIRCUMFLEX} Fixed Speed STBY", "i Fixed Speed STBY"),
    (f"{MINUS}1", "-1"), (f"Pre{EN_DASH}AF", "Pre-AF"), (f"{FULLWIDTH_HYPHEN}3", "-3"),
    (f"{GREEK_IOTA_CAP}SO", "ISO"), (f"{CYR_U_CAP}es", "Yes"),
    (f"P{CYR_ER_CAP}{CYR_ZE_CAP}", f"PP{CYR_ZE_CAP}"),      # a ZE has no Latin twin: kept (a code reads it as a 3)
    (f"Custom{SHARP_S} 7", f"Custom{SHARP_S} 7"),
    ("Cont. Shooting: Hi+", "Cont. Shooting: Hi+"),
    (f"-{RARROW}0{RARROW}+", f"-{RARROW}0{RARROW}+"),       # the camera's own signs stay
    (f"Add Rating ({STAR}{STAR})", f"Add Rating ({STAR}{STAR})"),
    (f"{PLUS_MINUS}0", f"{PLUS_MINUS}0"),
    (None, ""), ("", ""), ("   ", ""),
]


def test_canonical_cleans_a_reading_one_way_and_keeps_its_case():
    for raw, want in CLEANED:
        assert canonical(raw) == want, raw


def old_tables() -> dict:
    """The look-alike tables the kit kept before camkit.reading, by where they live."""
    import boxes_run
    import pass2_report
    from proving import screens
    from writer import labels
    return {"camkit.match.CYRILLIC": match.CYRILLIC, "camkit.match.LOOKALIKES": match.LOOKALIKES,
            "camkit.safety (the guards)": safety._GUARD_LOOKALIKES, "writer.labels.LATIN": labels.LATIN,
            "pass2_report.LOOKALIKE": pass2_report.LOOKALIKE, "provers.boxes_run.LOOKALIKE": boxes_run.LOOKALIKE,
            "proving.screens.CELL_LOOKALIKES": screens.CELL_LOOKALIKES}


# Where canonical does not do what an old table does, table by table, and why; it does every other entry alike
DIFFERS = {
    "pass2_report.LOOKALIKE": {RARROW: "the camera's own arrow is a sign and stays (pass2_report.norm drops it after)"},
    "proving.screens.CELL_LOOKALIKES": {CYR_ZE_CAP: "a digit's look-alike: taken in a code (code_same), never by canonical",
                                        CYR_ZE: "a digit's look-alike: taken in a code (code_same), never by canonical",
                                        "(": "a sign read for a code's C: taken in a code (code_same)"},
}
CASELESS = {"proving.screens.CELL_LOOKALIKES"}      # it upper-cases after (screens.cell_text_code)


def samples() -> list:
    """Readings to try the tables on: every character of every old table, CLEANED's, and a few whole labels."""
    chars = {chr(k) for t in old_tables().values() for k in t}
    return sorted(chars) + [raw for raw, _ in CLEANED if raw] + [
        f"F{CYR_O}rmat", f"Wi{NB_HYPHEN}Fi Direct", "Lo (E-Shutter)", f"{CYR_O_CAP}{CYR_KA_CAP}"]


def test_canonical_folds_every_letter_each_old_table_folds_but_where_it_says():
    for name, table in old_tables().items():
        for k, v in table.items():
            c, want = chr(k), (v if isinstance(v, str) else chr(v))
            got = canonical(c)
            if c in DIFFERS.get(name, {}):
                assert got == c and got != want, (name, f"U+{k:04X}")
                if name == "proving.screens.CELL_LOOKALIKES":
                    assert code_same(c, want), (name, f"U+{k:04X}")      # a code takes it
                continue
            assert (got.upper() == want.upper() if name in CASELESS else got == want), (name, f"U+{k:04X}", got, want)


def test_after_canonical_no_old_table_finds_anything_left_to_fold():
    """canonical is a superset of each table: the table applied after it changes nothing (its DIFFERS apart)."""
    for name, table in old_tables().items():
        rest = {k: v for k, v in table.items() if chr(k) not in DIFFERS.get(name, {})}
        for t in samples():
            c = canonical(t).lower() if name == "camkit.match.CYRILLIC" else canonical(t)    # match.key lowers first
            assert c.translate(rest) == c, (name, t)


def test_canonical_does_all_the_guards_fold_does_and_is_done_once():
    for t in samples():
        assert safety.fold(canonical(t)) == canonical(t), t
        assert canonical(canonical(t)) == canonical(t), t
    for k in safety._GUARD_LOOKALIKES:
        assert canonical(chr(k)) == safety.fold(chr(k)), f"U+{k:04X}"


def test_where_canonical_goes_further_than_the_guards_fold():
    """Accents, the letters marked "added" in camkit.reading, the quotation marks and primes, and the ends' spacing:
    each folds by canonical and not by safety.fold. A guard that takes canonical as one more reading gains these."""
    for raw in (I_CIRCUMFLEX, CYR_U_CAP, f"{RSQUO}", f"2{DOUBLE_PRIME}", RSAQUO, " Format ", f"Don{ACUTE}t"):
        assert canonical(raw) != safety.fold(raw), raw


def test_a_guard_takes_canonical_beside_the_reading_never_instead():
    """As safety.fold, canonical can hide a slip: a circled one before "lnitialize" becomes a digit glued to the l,
    and the l at a word's start is no longer read as an I. So a guard judges canonical beside the raw reading (it can
    only add a refusal), never in its place; and every never-open label that is refused as read is refused cleaned
    too, the slip apart."""
    raw = f"{CIRCLED_ONE}lnitialize"
    assert safety.never_open(raw) and canonical(raw) == "1lnitialize" and not safety.never_open(canonical(raw))
    for t in (f"F{CYR_O}rmat", FULLWIDTH_FORMAT, f"Wi{NB_HYPHEN}Fi Direct", f"For{ZWSP}mat", f"{GREEK_IOTA_CAP}nitialize",
              "Forrnat", "Delete AII", "Format.", f"Pre{EN_DASH}AF"):
        assert safety.never_open(t) and safety.never_open(canonical(t)), t


def test_what_match_key_will_change_once_it_takes_canonical():
    """camkit.match.key (option labels, find_row, enter_pp) folds a few look-alikes itself. Repointed at canonical
    (the next step, after the census), these readings key as their Latin spelling, where today they do not; the
    first list keys alike already."""
    for t in (f"{CYR_ES_CAP}.Temp./Filter", f"120{CYR_ER}", f"{CYR_U_CAP}es", f"2{DOUBLE_PRIME}", "2''", f"2{RDQUO}",
              "Lo (E-Shutter)"):
        assert match.key(canonical(t)) == match.key(t), t
    changes = {f"{GREEK_IOTA_CAP}SO": "ISO", f"{I_CIRCUMFLEX}Auto": "iAuto", f"Pre{EN_DASH}AF": "Pre-AF",
               FULLWIDTH_FORMAT: "FORMAT", f"A {RSAQUO} B": "A > B", f"Don{RSQUO}t": "Don't"}
    for t, latin in changes.items():
        assert match.key(t) != match.key(latin) and match.key(canonical(t)) == match.key(latin), t


def test_what_page_model_key_text_will_change_once_it_takes_canonical():
    """page_model.key_text (at_label, closest_row, the page model's vote, pass-1 agreement) folds no look-alike letter
    at all; it mends the angle quote and the apostrophe. Repointed at canonical, a Cyrillic or Greek letter keys as
    its Latin twin."""
    import page_model
    for t in (f"Shooting {RSAQUO} Menu", f"Don{RSQUO}t show", "SAF Frame Move Amt"):
        assert page_model.key_text(canonical(t)) == page_model.key_text(t), t
    changes = {f"{CYR_ES_CAP}.Temp./Filter": "C.Temp./Filter", f"F{CYR_O}cus Area": "Focus Area",
               f"{GREEK_IOTA_CAP}SO AUTO": "ISO AUTO", f"Pre{EN_DASH}AF": "Pre-AF", FULLWIDTH_FORMAT: "FORMAT"}
    for t, latin in changes.items():
        assert page_model.key_text(t) != page_model.key_text(latin), t
        assert page_model.key_text(canonical(t)) == page_model.key_text(latin), t


def test_every_look_alike_is_one_canonical_sees():
    """A table entry that NFKC changes would never be met (canonical takes NFKC first): none is."""
    for c, latin in reading._LETTERS.items():
        assert not c.isascii() and unicodedata.normalize("NFKC", c) == c, f"U+{ord(c):04X}"
        assert len(latin) == 1 and latin.isascii() and latin.isalpha() and canonical(c) == latin, f"U+{ord(c):04X}"


def test_the_rule_and_its_census_hold_no_character_a_reader_could_take_for_another():
    for p in ("kit/camkit/reading.py", "kit/tools/reader_census.py", "kit/tests/test_reading.py"):
        assert (ROOT / p).read_text(encoding="utf-8").isascii(), p


# ---------------------------------------------------------------------------------------------- doubts and agreement

DOUBTS = [
    ("Golden Ratio Grid", "label", ["Off", "Golden Ratio Grid"], []),
    ("XAVC S 4K", "label", ["XAVC S 4K", "XAVC HS 4K"], []),
    ("1/250", "number", ["1/250", "1/4000"], []),
    (f"{CYR_ES_CAP}.Temp./Filter", "label", ["Auto", "C.Temp./Filter"], ["lookalike: CYRILLIC CAPITAL LETTER ES"]),
    (f"P{CYR_ER_CAP}{CYR_ZE_CAP}", "code", ["PP1", "PP2", "PP3"],
     ["lookalike: CYRILLIC CAPITAL LETTER ER", "foreign: CYRILLIC CAPITAL LETTER ZE", "short: 3"]),
    (f"Custom{SHARP_S} 7", "label", [], ["foreign: LATIN SMALL LETTER SHARP S"]),
    (f"{CJK} Auto", "label", [], ["foreign: CJK UNIFIED IDEOGRAPH-4E2D"]),
    (f"{I_CIRCUMFLEX} Fixed Speed STBY", "label", [], ["lookalike: LATIN SMALL LETTER I WITH CIRCUMFLEX"]),
    ("8", "number", ["7", "8", "9"], ["short: 1"]),
    ('10"', "number", [], ["short: 3"]),
    ("Off", "label", ["Off", "On"], ["short word: 3"]),
    ("Minimum", "number", [], ["no number"]),
    ("PP1O", "code", ["PP1", "PP10"], ["letter by digit: 1O"]),
    ("F2.o", "label", ["F2.8", "F4.0"], ["letter by digit: 2.o", "no option"]),
    ("Fixed Speed SBY", "label", ["Fixed Speed STBY", "Fixed Speed REC"], ["no option"]),
    ("Contimuous Shooting", "label", ["Continuous Shooting", "Single Shooting"], ["loose"]),
    ("Standard", "label", ["Standard", "Standard"], ["several options: 2"]),
    ("You can perform detailed settings", "text", [], []),
    ("OK", "text", [], []),
    # a character the cleaning changes is a doubt even where it makes no letter Latin: a symbol spelled out in letters,
    # a combining mark on its own, an invisible character; dashes, quotation marks and spacing are not
    (f"{CIRCLED_M}ode Dial", "label", [], ["cleaned: CIRCLED LATIN CAPITAL LETTER M"]),
    (f"{NUMERO} Setting", "label", [], ["cleaned: NUMERO SIGN"]),
    (f"For{ZWSP}mat", "label", [], ["cleaned: ZERO WIDTH SPACE"]),
    (f"{COMBINING_TILDE}Square Grid", "label", [], ["cleaned: COMBINING TILDE"]),
    (f"{FULLWIDTH_FORMAT[0]}ormat", "label", [], ["lookalike: FULLWIDTH LATIN CAPITAL LETTER F"]),
    (f"Wi{NB_HYPHEN}Fi{NBSP}Direct", "label", [], []),
    (f"Don{RSQUO}t show this again", "text", [], []),
    (f"Add Rating ({STAR}{STAR})", "label", [], []),
    (f"{MINUS}{PLUS_MINUS}0 EV", "number", [], []),
]


def test_doubts_name_why_ocr_alone_is_not_enough():
    for text, expect, choices, want in DOUBTS:
        assert doubts(text, expect, choices=choices, lit=True) == want, text


def test_an_empty_reading_is_a_doubt_only_where_something_is_lit():
    assert doubts("", "label", lit=True) == ["empty"] and doubts("  ", "number") == []
    with pytest.raises(ValueError):
        doubts("Auto", "word")


def test_low_confidence_counts_only_once_its_floor_is_set(monkeypatch):
    from camkit.ocr import Line
    lines = [Line("Golden Ratio Grid", 0.3, 0, 0, 10, 10)]
    assert doubts("Golden Ratio Grid", "label", lines=lines) == []
    monkeypatch.setattr(reading, "CONF_FLOOR", 0.5)
    assert doubts("Golden Ratio Grid", "label", lines=lines) == ["low confidence: 0.30"]


AGREE = [
    (f"{CYR_ES_CAP}.Temp./Filter", "C.Temp./Filter", "label", [], True),
    ("Cont. Shooting: Hi+", "Cont. Shooting: Lo", "label", [], False),
    ("Lo", "10", "label", [], False),
    ("Spot Large", "Spot: Large", "label", ["Spot: Large", "Spot: Small"], True),
    ("Spot Small", "Spot: Large", "label", ["Spot: Large", "Spot: Small"], False),
    ("", "Auto", "label", [], False),
    (f"Add Rating ({STAR}{STAR})", "Add Rating (**)", "label", [], False),
    (f"Add Rating ({STAR}{STAR})", f"Add Rating ( {STAR}{STAR} )", "label", [], True),
    (f"Add Rating ({STAR}{STAR})", f"Add Rating ({STAR})", "label", [], False),
    ("1/4000", "1/400", "number", [], False),
    (f"{MINUS}1", "-1", "number", [], True),
    (f"{PLUS_MINUS}0", "0", "number", [], True),
    (f"{DOUBLE_DAGGER}0", "+0", "number", [], True),
    ("+2", "2", "number", [], True),
    ("80%", "80", "number", [], True),
    ("8", "8", "number", ["7", "8", "9"], True),
    (f"P{CYR_ER_CAP}{CYR_ZE_CAP}", "PP3", "code", [], True),
    ("PP1O", "PP10", "code", [], False),          # an O after a digit is a ring (PP1) or a 0: no options, neither
    ("PP1O", "PP10", "code", ["PP10", "PP11"], True),
    ("PP1O", "PP10", "code", ["PP1", "PP10"], False),
    ("PP1O", "PP1", "code", [], False),
    ("(1", "C1", "code", [], True),
    ("XL.", "XL", "code", [], True),
    ("XS", "XL", "code", [], False),
    ("0K", "OK", "button", [], True),
    (f"{CYR_O_CAP}{CYR_KA_CAP}", "OK", "button", [], True),
    ("Cancel", "OK", "button", [], False),
    ("Movie Settings", "movie  settings", "text", [], True),
    # without options, a label agrees by its key, never by match.same's likeness alone
    ("Spot Large", "Spot: Large", "label", [], False),
    ("Not registered", "Registered", "label", [], False),
    ("Compressed", "Uncompressed", "label", [], False),
    ("Display Main Menu", "Display My Menu", "label", [], False),
    ("Av (Av in M mode)", "Tv (Tv in M mode)", "label", [], False),
    (f"{CYR_ES_CAP}.Temp./Filter", "c.temp/filter", "label", [], True),
    # a point between digits is part of a code: F1.1 is never F11
    ("F1.1", "F11", "code", [], False),
    ('1.3"', '13"', "code", [], False),
    ("F1.4", "F14", "label", [], False),
    # a sign or a star more or less is another button or text, and options count for them too
    ("Hi+", "Hi", "button", [], False),
    ("Hi+", "Hi", "text", [], False),
    ("+0.3EV", "-0.3EV", "text", [], False),
    (f"Rating ({STAR}{STAR})", f"Rating ({STAR})", "text", [], False),
    ("OK.", "OK", "button", [], True),
    ("Cancel", "OK", "button", ["OK", "Cancel"], False),
    ("movie settings", "Movie Settings", "text", ["Movie Settings", "Still Settings"], True),
    (f"Move AF Frame {LR_ARROW}: L", f"Move AF Frame {UD_ARROW}: L", "number", [], False),
    # a point between a digit and a letter read for a digit stays: OCR's l, I or S after the point is no way to F11
    ("F1.l", "F11", "label", [], False),
    ("F1.I", "F11", "label", [], False),
    ("F2.S", "F25", "label", [], False),
    ("F1.l", "F11", "code", [], False),
    ("F2.S", "F25", "code", [], False),
    ("Cont.Shooting: Hi", "Cont. Shooting: Hi", "label", [], True),     # a point between words is no decimal point
    ("4:3", "43", "number", [], False),
    ("4:2:2", "422", "number", [], False),
]


def test_agree_by_the_kind_of_thing_read():
    for a, b, expect, choices, want in AGREE:
        assert agree(a, b, expect, choices) is want, (a, b, expect)
        assert agree(b, a, expect, choices) is want, (b, a, expect)


def test_no_two_options_of_one_setting_ever_agree():
    """Every pair of distinct options of one setting in the a1 II's definition (each setting's list of labels, the
    lists two settings share read once) is two things to agree(), by every kind of thing read, with the setting's
    options and without any: a reading that agreed with both could stand for the wrong one."""
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    lists = {tuple(dict.fromkeys(str(lab) for _, lab in s.get("values") or [] if lab is not None))
             for s in doc["settings"]}
    pairs = 0
    for opts in lists:
        for i, a in enumerate(opts):
            for b in opts[i + 1:]:
                pairs += 1
                for kind in reading.EXPECTS:
                    assert not agree(a, b, kind), (a, b, kind, "without options")
                    assert not agree(a, b, kind, opts), (a, b, kind, "with the setting's options")
    assert pairs > 100000


def look_alike_misreads(option: str) -> set:
    """An option with each of its digits read as each character OCR takes for that digit (camkit.reading's _DIGITS,
    every entry), one digit at a time, and its first two digits at once in every pairing."""
    looks = {}
    for c, d in reading._DIGITS.items():
        looks.setdefault(d, []).append(c)
    at = [i for i, c in enumerate(option) if c in looks]
    out = {option[:i] + c + option[i + 1:] for i in at for c in looks[option[i]]}
    if len(at) >= 2:
        i, j = at[:2]
        out |= {option[:i] + a + option[i + 1:j] + b + option[j + 1:] for a in looks[option[i]] for b in looks[option[j]]}
    out.discard(option)
    return out


def test_a_digit_read_as_a_look_alike_never_names_another_option():
    """Every option of the a1 II's definition with its digits read as look-alikes (look_alike_misreads: the thin
    strokes and the letters, Latin, Cyrillic and Greek, one digit and two at once) never names another option of its
    setting, and never agrees with one, as a label, a number or a code. It may name its own option, or none (a doubt the
    reader settles). "1/|25" is 1/125, never 1/25; "F|4" F14, never F4; "I5 Sec" 15 Sec, never 5 Sec. A point lost
    whole is not tried here: "F11" read for F1.1 is the other option's own text, which no rule on the text can tell."""
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    lists = {tuple(dict.fromkeys(str(lab) for _, lab in s.get("values") or [] if lab is not None))
             for s in doc["settings"]}
    tried = 0
    for opts in lists:
        for k, o in enumerate(opts):
            for m in look_alike_misreads(o):
                tried += 1
                for kind in ("label", "number", "code"):
                    assert reading.choice_of(m, kind, opts) in (None, k), (m, o, kind)
                    assert not any(agree(m, q, kind) for q in opts if q != o), (m, o, kind)
    assert tried > 1000


# Cyrillic letters the readers write for Latin ones, by the Latin letter (each named by its code point)
CYRILLIC_FOR = {lat: chr(cp) for lat, cp in (
    ("a", 0x430), ("e", 0x435), ("o", 0x43E), ("p", 0x440), ("c", 0x441), ("x", 0x445), ("y", 0x443), ("A", 0x410),
    ("B", 0x412), ("C", 0x421), ("E", 0x415), ("H", 0x41D), ("K", 0x41A), ("M", 0x41C), ("O", 0x41E), ("P", 0x420),
    ("T", 0x422), ("X", 0x425), ("i", 0x456), ("I", 0x406), ("S", 0x405))}


def renderings(o: str) -> dict:
    """An option as a reader or OCR really writes it: Cyrillic look-alikes (all, and one), a stop after it, doubled
    spaces, a space dropped, lower and upper case, spaces round it, the plus-minus zero's other forms, a radio ring read
    as "0 " or "o " or a bullet before it, the seconds mark as two apostrophes, a double prime or a quotation mark, an
    en dash for a hyphen, a curly apostrophe, a space between a letter and a digit."""
    out = {}
    if any(c in CYRILLIC_FOR for c in o):
        out["cyrillic all"] = "".join(CYRILLIC_FOR.get(c, c) for c in o)
        i = next(i for i, c in enumerate(o) if c in CYRILLIC_FOR)
        out["cyrillic one"] = o[:i] + CYRILLIC_FOR[o[i]] + o[i + 1:]
    if not o.endswith("."):
        out["trailing dot"] = o + "."
    if " " in o:
        out["doubled spaces"] = o.replace(" ", "  ")
        out["space dropped"] = o.replace(" ", "", 1)
    out["lower"], out["upper"], out["padded"] = o.lower(), o.upper(), f"  {o} "
    if re.fullmatch(PLUS_MINUS + r"0(\.0+)?( ?\w+)?", o):
        for how, sign in (("I for the sign", "I"), ("double dagger", DOUBLE_DAGGER), ("plus", "+"), ("minus", "-"),
                          ("plus and minus", "+-")):
            out[how] = sign + o[1:]
    out["zero ring before"], out["o ring before"], out["bullet before"] = "0 " + o, "o " + o, chr(0x2022) + " " + o
    if o.endswith('"'):
        out["seconds as two apostrophes"] = o[:-1] + "''"
        out["seconds as a double prime"] = o[:-1] + DOUBLE_PRIME
        out["seconds as a quotation mark"] = o[:-1] + RDQUO
    if "-" in o:
        out["en dash"] = o.replace("-", EN_DASH)
    if "'" in o:
        out["curly apostrophe"] = o.replace("'", RSQUO)
    if re.search(r"[A-Za-z]\d|\d[A-Za-z]", o):
        out["space between letter and digit"] = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", o, count=1)
    return out


def why_unnamed(how: str, rendering: str, option: str, opts: tuple, with_options: bool) -> str | None:
    """Why a rendering may fail to name its own option: only where it is also a reading of another option, so that
    false agreement must lose (a refusal the reader settles). None for any other failure."""
    if how == "zero ring before" and option[:1].isdigit():
        if not with_options:
            return "a zero and a space before a digit is a ring, or a point read as a space: with no options, neither"
        if f"0.{option}" in opts:
            return f"it is also 0.{option} with its point read as a space, an option of the same setting"
    if how == "I for the sign" and re.match(r"I0(?![\d.])", rendering):
        if not with_options:
            return "an I before a bare zero is a 1 (10) or the plus-minus sign: with no options, neither"
        if "1" + rendering[1:] in opts:
            return f"it is also 1{rendering[1:]}, an option of the same setting"
    return None


# every rendering that names no option of its setting although that setting has options to name: each a reading of
# another option too (why_unnamed), so refused
CONFLICTS_WITH_OPTIONS = {
    ('0 4"', '4"'), ('0 5"', '5"'), ('0 6"', '6"'), ('0 8"', '8"'),
}


def test_every_option_names_itself_as_readers_and_ocr_write_it():
    """True agreements, the other side of the rules: every option of the a1 II's definition, written as a reader or OCR
    really writes it (renderings), names itself among its setting's options and agrees with itself without options,
    as a label and as the kind kit/tools/reader_census.py takes it for. Where a rendering is also a reading of another
    option, false agreement loses: why_unnamed says why, and the ones with options are all in CONFLICTS_WITH_OPTIONS."""
    import reader_census
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    lists = {tuple(dict.fromkeys(str(lab) for _, lab in s.get("values") or [] if lab is not None))
             for s in doc["settings"]}
    tried, conflicts = 0, set()
    for opts in lists:
        for k, o in enumerate(opts):
            kinds = {"label", reader_census.expect_of({"label": o})}
            for kind in kinds:
                assert reading.choice_of(o, kind, opts) == k, (o, kind)
            for how, r in renderings(o).items():
                for kind in kinds:
                    tried += 1
                    if reading.choice_of(r, kind, opts) != k:
                        assert why_unnamed(how, r, o, opts, True), (how, r, o, kind, "with options")
                        conflicts.add((r, o))
                    if not agree(r, o, kind):
                        assert why_unnamed(how, r, o, opts, False), (how, r, o, kind, "without options")
    assert conflicts == CONFLICTS_WITH_OPTIONS and tried > 40000


def option_lists(menu_groups: bool = False) -> list:
    """Each setting's list of option labels in the a1 II's definition, each list once, in a fixed order; with
    menu_groups, also each menu page group's row labels (the options a row search is given)."""
    doc = json.loads((ROOT / "editor" / "definitions" / "ILCE-1M2_fw4.00.json").read_text(encoding="utf-8"))
    lists = {tuple(dict.fromkeys(str(lab) for _, lab in s.get("values") or [] if lab is not None))
             for s in doc["settings"]}
    if menu_groups:
        groups = {}
        for row in doc.get("menu") or []:
            groups.setdefault((row["tab"], row["group"]), []).append(row["label"])
        lists |= {tuple(dict.fromkeys(v)) for v in groups.values()}
    return sorted(lists)


def decorations(o: str) -> dict:
    """What the screen draws round an option and OCR reads as text, and the readings a text allows two ways: rings,
    bullets and zeros before it, stops, rings and zeros after it, a glued o or O, the plus-minus zero's forms, a 1
    read as I or a thin stroke, a leading 0 read as O."""
    out = {f"prefix {p!r}": p + o for p in (chr(0x2022) + " ", chr(0xB7) + " ", chr(0x25E6) + " ", chr(0x25CF) + " ",
                                            chr(0x25CB) + " ", "o ", "O ", "0 ", "o", "O", "0", "00 ", "0  ")}
    out |= {f"suffix {s!r}": o + s for s in (".", ":", "..", " .", " o", " O", " 0", "0", "o", ". o", ":.")}
    if re.match(r"\d", o):
        out["ring 0 and a space before a digit"], out["ring O glued before a digit"] = "0 " + o, "O" + o
    if re.match(r"0\.", o):
        out["point read as a space"], out["point dropped"] = "0 " + o[2:], "0" + o[2:]
    if re.match(r"1\d", o):
        out["1 read as I"], out["1 read as a thin stroke"] = "I" + o[1:], "|" + o[1:]
    if o.startswith(PLUS_MINUS):
        for how, sign in (("I", "I"), ("thin stroke", "|"), ("plus", "+"), ("dropped", ""), ("dagger", DOUBLE_DAGGER)):
            out[f"plus-minus as {how}"] = sign + o[1:]
    if o.startswith("0"):
        out["leading 0 read as O"], out["leading 0 read as o"] = "O" + o[1:], "o" + o[1:]
    return out


def test_a_decorated_option_names_only_itself_or_nothing():
    """Every option list of the a1 II's definition and every menu page group, a fixed sample of each list's options
    (at most six, spread over the list), each decorated as OCR reads what the screen draws round it (decorations):
    never names another option of its list, and never agrees with one without options, as a label, a number or a code.
    The one thing allowed is a decorated text that is another option's own text: "1/25" with a 0 glued after it is
    1/250, which no rule on the text can tell from 1/250 (decision 22, what the rule cannot catch)."""
    tried = 0
    for opts in option_lists(menu_groups=True):
        step = max(1, len(opts) // 6)
        for k in range(0, len(opts), step):
            o = opts[k]
            for how, m in decorations(o).items():
                if m in opts and m != o:
                    continue                                # another option's own text
                for kind in ("label", "number", "code"):
                    tried += 1
                    assert reading.choice_of(m, kind, opts) in (None, k), (how, m, o, kind)
                    assert not any(agree(m, q, kind) for q in opts if q != o), (how, m, o, kind)
    assert tried > 50000


def test_two_readings_of_one_text_agree_with_nothing_without_options():
    """A text the readers allow two ways (camkit.reading._variants) names an option only where the options hold one of
    them, and without options agrees with nothing: "I0" is 10 or the plus-minus zero, "1/25o" 1/25 or 1/250, "OS&Q
    Record Setting" S&Q Record Setting with a ring glued before it."""
    for a, b in (("I0", "10"), ("I0 EV", "10 EV"), (f"{PLUS_MINUS}0", "I0"), ("1/25o", "1/250"), ("1/25o", "1/25"),
                 ("OS&Q Record Setting", "S&Q Record Setting"), ("0 4\"", "4\"")):
        for kind in ("label", "number", "code"):
            assert not agree(a, b, kind) and not agree(b, a, kind), (a, b, kind)
    assert reading.choice_of("1/25o", "number", ["1/25", "1/250"]) is None
    assert reading.choice_of("1/25o", "code", ["1/25", "1/250"]) is None
    assert reading.choice_of("1/25o", "label", ["1/250", "1/500"]) == 0
    assert reading.choice_of("ISO 100o", "label", ["ISO 100", "ISO 1000"]) is None
    assert reading.choice_of("OS&Q Record Setting", "label", ["Record Setting", "S&Q Record Setting"]) == 1
    assert reading.choice_of("I0", "label", ["10", f"{PLUS_MINUS}0"]) is None
    assert reading.choice_of("I0", "label", [f"{PLUS_MINUS}0", "+1"]) == 0


def test_a_rating_names_an_option_only_with_the_same_stars():
    """agree's star rule holds for naming too: a reading with stars names a star option only when it reads alike but
    for spacing, case and the ring; never by likeness. "Rating (2 stars)o" named "Rating (3 stars)" loosely, and with
    the reader saying 3 stars the vote stood on one eye (fifth review, 2026-11-13)."""
    ratings = [f"Rating ({STAR * n})" for n in range(1, 6)]
    for said in (f"Rating ({STAR}{STAR})o", f"Rating ({STAR}{STAR}))", f"Rating ({STAR}{STAR} {STAR})x"):
        assert reading.choice_of(said, "label", ratings) is None, said
    assert reading.choice_of(f"o Rating ( {STAR}{STAR} ).", "label", ratings) == 1
    assert reading.choice_of("Rating (**)", "label", ratings) is None


def test_a_rating_read_apart_never_stands_on_one_eye(eyes):
    """The fifth review's case through read(): OCR "Rating (2 stars)o", the reader "Rating (3 stars)". OCR's reading
    names no option (stars name one only alike), so the two are apart, and with no third vote the row stops."""
    ratings = [f"Rating ({STAR * n})" for n in range(1, 6)]
    f = eyes.frame("00090_down.png")
    eyes.see(f, f"Rating ({STAR}{STAR})o", box=CAROUSEL.box)
    eyes.answer("option", {"selected": f"Rating ({STAR * 3})"})
    r = reading.read(f, CAROUSEL, "label", "proof", choices=ratings)
    assert r.refused.startswith(reading.DISAGREE) and (r.by, r.choice, r.agreed) == ("none", None, [])


def test_votes_and_agree_never_part(eyes):
    """INVARIANT over many generated readings, for every kind: whenever read() lets a reading stand on votes, two or
    more independent sources stand behind it, and every vote it counts as agreeing agrees (agree) with what stood and
    with every other such vote. tally and agree are one predicate, so they cannot part again. Votes are OCR, the
    reader, the second OCR engine and a third reader of another model, drawn from each list's options, their
    decorations, look-alike misreads and other options; the star demonstration among them."""
    eyes.second = "rapidocr"
    eyes.models["third"] = "other-model"
    said_by = {}

    def answer(role):
        return lambda image: {"selected": said_by.get((role, image))}
    eyes.answer("option", answer("second"))
    eyes.answer("option", answer("third"), role="third")
    ratings = tuple(f"Rating ({STAR * n})" for n in range(1, 6))
    cases = [(ratings, "label", f"Rating ({STAR}{STAR})o", f"Rating ({STAR * 3})", "", "")]
    for opts in option_lists()[::3]:
        if len(opts) < 2:
            continue
        o, q = opts[0], opts[len(opts) // 2]
        pool = [o, q, *sorted(decorations(o).values())[:3], *sorted(look_alike_misreads(o))[:2], ""]
        for kind in ("label", "number", "code"):
            for i, ocr_text in enumerate(pool):
                cases.append((opts, kind, ocr_text, pool[(i + 1) % len(pool)], pool[(i + 2) % len(pool)],
                              pool[(i + 3) % len(pool)]))
    stood = 0
    for n, (opts, kind, ocr_text, reader_text, ocr2_text, third_text) in enumerate(cases):
        f = eyes.frame(f"inv{n:05d}.png")
        if ocr_text:
            eyes.see(f, ocr_text, box=CAROUSEL.box)
        if ocr2_text:
            eyes.see(f, ocr2_text, box=CAROUSEL.box, eng="rapidocr")
        image = f.path.read_bytes()
        said_by[("second", image)], said_by[("third", image)] = reader_text, third_text
        r = reading.read(f, CAROUSEL, kind, "proof", choices=opts)
        if r.refused or r.by != "votes":
            continue
        stood += 1
        counted = [v for v in r.votes if v.frame == r.frame and v.eye in r.agreed]
        assert r.independent() >= 2, (kind, ocr_text, reader_text, ocr2_text, third_text, r.agreed)
        assert all(agree(v.text, r.text, kind, opts) for v in counted), (kind, ocr_text, reader_text, r.text)
        assert all(agree(a.text, b.text, kind, opts) for a, b in itertools.combinations(counted, 2))
    assert len(cases) > 1000 and stood > 50, (len(cases), stood)


def test_number_key_is_the_scale_rule_and_keeps_a_fraction():
    """number_key is what pass2_report.scale_key(scale_clean()) makes of a scale's number (the next step moves that
    rule here), but keeps "/" and the seconds mark, and reads full-width digits through NFKC."""
    import pass2_report as R
    for t in ("+2", "2", "-1", f"{MINUS}1", f"{EN_DASH}1", f"{FULLWIDTH_HYPHEN}3", f"{PLUS_MINUS}0", f"{DOUBLE_DAGGER}0",
              "+-0", "+0", "-0", "0", "80%", "80", "-15", "+15", "1.5", "Fast", ""):
        assert number_key(t) == R.scale_key(R.scale_clean(t)), t
    assert number_key("1/250") == "1/250" != R.scale_key(R.scale_clean("1/250"))
    assert number_key('2"') == '2"' and number_key("4:3") == "4:3" and number_key("4 :") == "4"
    assert number_key("-0.0") == number_key("+0.00") == "0" != R.scale_key(R.scale_clean("-0.0"))
    assert number_key(FULLWIDTH_TWO) == "2" != R.scale_key(R.scale_clean(FULLWIDTH_TWO))


def test_codes_take_every_digit_look_alike_the_picture_profile_rule_takes():
    for k, d in safety.PROFILE_DIGIT_LOOKALIKES.items():
        c = chr(k)
        assert code_same(f"PP{c}", f"PP{d}") and canonical(c) != d, f"U+{k:04X}"
    assert safety.profile_label_kind(f"P{CYR_ER_CAP}{CYR_ZE_CAP}") == ("profile", "PP3")


def test_codes_agree_where_the_axis_cells_read_alike():
    from proving import screens
    for raw, code in ((f"{CYR_ES_CAP}{CYR_ZE_CAP}", "C3"), ("(1", "C1"), (f"{CYR_HA_CAP}S", "XS"), (CYR_EM, "M")):
        assert screens.cell_text_code(raw) == code and code_same(raw, code), raw


def test_what_the_rule_makes_of_two_readings():
    labels = ["Lo", "Mid", "Hi"]
    assert reading.outcome("Middle Speed", None, "label") == "plain"
    assert reading.outcome("Lo", "Lo", "label", labels) == "stands on both"
    assert reading.outcome("", "Hi", "label", labels) == "stands on one reader"
    assert reading.outcome("", "8", "number") == "one reader, no options"                # nothing to name
    assert reading.outcome("Xq", "Hi", "label", labels) == "ocr names no option"         # refused as apart
    assert reading.outcome("Lo", "Hi", "label", labels) == "readers apart"
    assert reading.outcome("Lo", None, "label", labels) == "reader needed"
    assert reading.outcome("", "Max", "label", labels) == "readers apart"                # the reader names none
    assert set(reading.APART) <= set(reading.OUTCOMES)


# ---------------------------------------------------------------------------------------------- votes

def test_a_reading_stands_on_two_independent_votes_and_one_source_votes_once():
    V = reading.Vote
    labels = ["Lo", "Mid", "Hi"]
    win, eyes_ = reading.tally([V("ocr", "ocr:apple", "Lo"), V("reader", "reader:m1", "Hi"),
                                V("ocr2", "ocr:rapidocr", "Hi")], "label", labels)
    assert (win.text, eyes_) == ("Hi", ("reader", "ocr2"))
    same_model = [V("ocr", "ocr:apple", "Lo"), V("reader", "reader:m1", "Hi"), V("third", "reader:m1", "Hi")]
    assert reading.tally(same_model, "label", labels) == (None, ())          # two readers of one model: one vote
    tie = [V("ocr", "ocr:apple", "Lo"), V("ocr2", "ocr:rapidocr", "Lo"), V("reader", "reader:m1", "Hi"),
           V("third", "reader:m2", "Hi")]
    assert reading.tally(tie, "label", labels) == (None, ())
    unnamed = [V("ocr", "ocr:apple", "Max"), V("ocr2", "ocr:rapidocr", "Max"), V("reader", "reader:m1", "Hi")]
    assert reading.tally(unnamed, "label", labels) == (None, ())               # what names no option backs nothing
    assert reading.tally([V("ocr", "ocr:apple", "8"), V("check", "check:site", "8")], "number")[0].text == "8"


def test_without_options_votes_stand_only_as_a_group_that_agrees_in_every_pair():
    """agree is not transitive for codes, so without options a reading leant to by two votes that contradict each other
    stands for neither: "PPB" agrees with "PP8" and with "PPb" (8 and 6), which do not agree. A label's rule is: its
    digits must match, so "Lo", "L0" and "10" agree in no pair."""
    V = reading.Vote
    lo = [V("ocr", "ocr:apple", "Lo"), V("ocr2", "ocr:rapidocr", "L0"), V("reader", "reader:m1", "10")]
    assert not any(agree(a.text, b.text, "label") for a, b in itertools.combinations(lo, 2))   # digits must match
    assert reading.tally(lo, "label") == (None, ())
    pp = [V("ocr", "ocr:apple", "PP8"), V("ocr2", "ocr:rapidocr", "PPB"), V("reader", "reader:m1", "PPb")]
    assert agree("PP8", "PPB", "code") and agree("PPB", "PPb", "code") and not agree("PP8", "PPb", "code")
    assert reading.tally(pp, "code") == (None, ())
    both = [V("ocr", "ocr:apple", "PP8"), V("ocr2", "ocr:rapidocr", "PPB"), V("reader", "reader:m1", "PP3")]
    assert reading.tally(both, "code")[1] == ("ocr", "ocr2")


def test_one_ocr_engine_is_one_vote_whatever_name_it_goes_by(eyes):
    """camkit.ocr.read runs Apple Vision for any engine name but "rapidocr", while camkit.ocr.second() compares the raw
    names: an engine configured as "Apple" would make "apple" the second engine, and Apple would vote twice. Only the
    two names ocr.read knows are taken, and a second engine that is the first is no vote."""
    assert reading.engine_of("apple") == "apple" and reading.engine_of("rapidocr") == "rapidocr"
    for name in ("Apple", "vision", "RapidOCR", "", None):
        with pytest.raises(ValueError):
            reading.engine_of(name)
    f = eyes.frame("00040_down.png")
    eyes.see(f, "Lo", box=CAROUSEL.box)
    eyes.see(f, "Lo", box=CAROUSEL.box, eng="apple")
    eyes.answer("option", {"selected": "Hi"})
    eyes.engine = "Apple"
    with pytest.raises(ValueError):
        reading.read(f, CAROUSEL, "label", "proof", choices=["Lo", "Hi"])
    eyes.engine, eyes.second = "apple", "apple"
    r = reading.read(f, CAROUSEL, "label", "proof", choices=["Lo", "Hi"])
    assert r.refused.startswith(reading.DISAGREE) and [v.eye for v in r.votes] == ["ocr", "reader"]


def test_a_run_can_check_its_ocr_engines_before_it_presses(monkeypatch):
    from camkit import ConfigMissing, ocr
    monkeypatch.setattr(ocr, "engine", lambda: "apple")
    monkeypatch.setattr(ocr, "second", lambda: "rapidocr")
    assert reading.check_engines() == ("apple", "rapidocr")
    monkeypatch.setattr(ocr, "second", lambda: "apple")
    assert reading.check_engines() == ("apple", None)
    monkeypatch.setattr(ocr, "engine", lambda: "vision")
    with pytest.raises(ConfigMissing, match="the kit knows only 'apple' and 'rapidocr'"):
        reading.check_engines()


def test_a_reader_model_is_one_vote_whatever_its_case_and_spacing():
    assert reading.model_id(" Qwen3.8-27B ") == reading.model_id("qwen3.8-27b") != reading.model_id("qwen3.8-27b-4bit")


# ---------------------------------------------------------------------------------------------- read(), with the eyes faked

def test_a_plain_reading_stands_on_ocr_alone_and_the_reader_is_not_asked(eyes):
    f = eyes.frame("00001_right.png")
    eyes.see(f, "Golden Ratio Grid", box=CAROUSEL.box)
    r = reading.read(f, CAROUSEL, "label", "find", choices=["Off", "Golden Ratio Grid", "Square Grid"])
    assert (r.text, r.choice, r.by, r.refused, r.frame, eyes.asked) == ("Golden Ratio Grid", 1, "ocr", "", "00001_right.png", [])
    assert (r.agreed, r.independent()) == (["ocr"], 1)


def test_a_look_alike_asks_the_reader_first_and_stands_when_both_agree(eyes):
    f = eyes.frame("00002_right.png")
    eyes.see(f, f"{CYR_ES_CAP}.Temp./Filter", box=CAROUSEL.box)
    eyes.answer("option", {"title": "White Balance", "selected": "C.Temp./Filter"})
    r = reading.read(f, CAROUSEL, "label", "find", choices=["Auto", "C.Temp./Filter"])
    assert (r.text, r.choice, r.by, r.refused, eyes.asked) == ("C.Temp./Filter", 1, "both", "", ["option"])
    assert r.evidence() == {"by": "both", "ocr": f"{CYR_ES_CAP}.Temp./Filter", "reader": "C.Temp./Filter",
                            "reader_name": "fake second",
                            "votes": [{"eye": "ocr", "source": "ocr:apple", "text": f"{CYR_ES_CAP}.Temp./Filter",
                                       "frame": "00002_right.png"},
                                      {"eye": "reader", "source": "reader:fake-model", "text": "C.Temp./Filter",
                                       "frame": "00002_right.png"}],
                            "agreed": ["ocr", "reader"], "doubts": ["lookalike: CYRILLIC CAPITAL LETTER ES"]}


def test_a_short_number_ocr_dropped_stands_on_the_reader_for_a_proof_never_alone_for_a_press(eyes):
    where = reading.FIELD(0, (100, 178, 339, 233))
    f = eyes.frame("00003_up.png")                         # OCR reads nothing in the box
    eyes.answer("fields", {"title": "Frame Rate", "fields": ["8", "60p"], "active": 0})
    r = reading.read(f, where, "number", "proof", choices=["7", "8", "9"])
    assert (r.text, r.choice, r.by, r.refused, r.doubts, r.agreed) == ("8", 1, "reader", "", ["empty"], ["reader"])
    p = reading.read(f, where, "number", "press", choices=["7", "8", "9"])
    assert (p.by, p.refused, p.choice) == ("reader", "one reader's reading never decides a press alone", None)
    assert eyes.asked == ["fields"]                        # one question per frame and prompt in a process
    q = reading.read(f, where, "number", "press", choices=["7", "8", "9"], second=lambda frame: "8")
    assert (q.choice, q.refused, q.by, q.raw["second"], q.agreed, q.independent()) == \
        (1, "", "votes", "8", ["reader", "check"], 2)
    n = reading.read(f, where, "number", "proof")         # no options: a lone reader has nothing to name
    assert (n.refused, n.choice) == ("one reader's reading, with no options to check it against", None)


def test_two_readers_apart_read_a_fresh_frame_then_refuse_naming_every_reading(eyes):
    frames = [eyes.frame(f"0000{n}_down.png") for n in (4, 5, 6)]
    for f, said in zip(frames, ("Lo", "Lo", "Hi"), strict=True):
        eyes.see(f, said, box=CAROUSEL.box)
    eyes.answer("option", {"selected": "Hi"})
    grab = iter(frames).__next__
    r = reading.read(grab, CAROUSEL, "label", "proof", choices=["Lo", "Mid", "Hi"], fresh=1)
    assert r.refused == f"{reading.DISAGREE}: ocr 'Lo', reader 'Hi'" and r.choice is None and r.agreed == []
    assert (r.by, r.frame) == ("none", "00005_down.png")
    assert [(v.eye, v.frame) for v in r.votes] == [("ocr", "00004_down.png"), ("reader", "00004_down.png"),
                                                   ("ocr", "00005_down.png"), ("reader", "00005_down.png")]
    s = reading.read(grab, CAROUSEL, "label", "proof", choices=["Lo", "Mid", "Hi"])
    assert (s.text, s.choice, s.by, s.refused) == ("Hi", 2, "both", "")


def test_after_a_disagreement_a_plain_ocr_reading_is_one_more_vote_never_the_way_out(eyes):
    """Frame 1: OCR "Square Grid" with a Cyrillic IE, the reader "Golden Ratio Grid". Frame 2: OCR reads "Square Grid"
    plainly, the reader still "Golden Ratio Grid": OCR's plain reading does not end it in its favour; the third vote
    decides, or the row stops."""
    labels = ["Off", "Golden Ratio Grid", "Square Grid"]
    eyes.answer("option", {"selected": "Golden Ratio Grid"})
    frames = [eyes.frame(f"0005{n}_down.png") for n in range(4)]
    for f, said in zip(frames, (f"Squar{CYR_IE} Grid", "Square Grid") * 2, strict=True):
        eyes.see(f, said, box=CAROUSEL.box)
    grab = iter(frames).__next__
    r = reading.read(grab, CAROUSEL, "label", "press", choices=labels, fresh=1)
    assert r.refused.startswith(reading.DISAGREE) and r.choice is None and r.doubts == ["apart before"]
    eyes.second = "rapidocr"
    eyes.see(frames[3], "Golden Ratio Grid", box=CAROUSEL.box, eng="rapidocr")
    s = reading.read(grab, CAROUSEL, "label", "press", choices=labels, fresh=1)
    assert (s.text, s.choice, s.by, s.agreed) == ("Golden Ratio Grid", 1, "votes", ["reader", "ocr2"])
    assert "Square Grid" in s.texts()                      # every frame's readings are kept



def test_after_a_disagreement_a_lone_reader_does_not_win(eyes):
    """Frame 1: OCR "Lo", the reader "Hi". Frame 2: OCR reads nothing, the reader says "Hi" again: the reader alone
    does not settle what it was apart on, for a proof or a find; a second, independent vote does."""
    labels = ["Lo", "Mid", "Hi"]
    eyes.answer("option", {"selected": "Hi"})
    for stakes in ("proof", "find"):
        a, b = eyes.frame(f"0008{len(stakes)}a.png"), eyes.frame(f"0008{len(stakes)}b.png")
        eyes.see(a, "Lo", box=CAROUSEL.box)
        r = reading.read(iter([a, b]).__next__, CAROUSEL, "label", stakes, choices=labels, fresh=1)
        assert r.refused.startswith("the readers were apart on an earlier frame") and r.choice is None, stakes
        assert (r.by, r.independent()) == ("reader", 0)
    eyes.second = "rapidocr"
    c, d = eyes.frame("00089a.png"), eyes.frame("00089b.png")
    eyes.see(c, "Lo", box=CAROUSEL.box)
    eyes.see(d, "Hi", box=CAROUSEL.box, eng="rapidocr")
    s = reading.read(iter([c, d]).__next__, CAROUSEL, "label", "proof", choices=labels, fresh=1)
    assert (s.text, s.by, s.independent()) == ("Hi", "votes", 2)


def test_what_the_label_rules_name_and_what_they_leave_to_the_reader():
    """A leading I or thin stroke before a digit is a 1 (the plus-minus only before a zero with decimals); a zero before
    a digit (a radio ring, or a point lost) names no option; a reading that is one option's loose likeness and another's
    look-alike names neither."""
    secs = ["5 Sec", "15 Sec", "0.4\"", "4\""]
    assert reading.choice_of("I5 Sec", "label", secs) == 1 and reading.choice_of("|5 Sec", "label", secs) == 1
    assert reading.choice_of("04\"", "label", secs) is None and reading.choice_of("0 4\"", "label", secs) is None
    assert agree("I0.0", f"{PLUS_MINUS}0.0", "label") and not agree("I0", "0", "label")
    marks = ["Shot Mark Only", "Shot Mark1 Only", "Shot Mark2 Only"]
    assert reading.choice_of("Shot MarkZ Only", "label", marks) is None
    images = ["This Image", "1 / 2 This Image", "All Images"]
    assert reading.choice_of("l / Z This Image", "label", images) in (None, 1)       # never This Image
    assert reading.choice_of("1/|25", "number", ["1/25", "1/125"]) == 1
    assert reading.choice_of("F|4", "number", ["F4", "F14"]) == 1
    assert not agree("F1.|", "F11", "code") and not agree("F1 1", "F11", "code") and not agree("F1,1", "F11", "number")
    assert reading.choice_of("PP|1", "label", ["PP1", "PP11"]) == 1

def test_a_sites_own_check_is_one_more_vote_where_the_readers_are_apart(eyes):
    f = eyes.frame("00045_down.png")
    eyes.see(f, "Lo", box=CAROUSEL.box)
    eyes.answer("option", {"selected": "Hi"})
    r = reading.read(f, CAROUSEL, "label", "proof", choices=["Lo", "Mid", "Hi"], second=lambda frame: "Hi")
    assert (r.text, r.by, r.agreed, r.independent()) == ("Hi", "votes", ["reader", "check"], 2)


def test_the_third_vote_is_the_second_ocr_engine_then_a_reader_of_another_model(eyes):
    """OCR and the reader apart on the last frame: the second OCR engine votes; where it settles nothing, a reader of
    another model (the "third" role); a "third" reader of the second's own model is never asked, for it would be one
    vote twice."""
    labels = ["Lo", "Mid", "Hi"]
    eyes.answer("option", {"selected": "Hi"})
    eyes.second = "rapidocr"
    f = eyes.frame("00020_down.png")
    eyes.see(f, "Lo", box=CAROUSEL.box)
    eyes.see(f, "Hi", box=CAROUSEL.box, eng="rapidocr")
    r = reading.read(f, CAROUSEL, "label", "proof", choices=labels)
    assert (r.text, r.choice, r.by, r.refused, r.agreed, r.independent()) == ("Hi", 2, "votes", "", ["reader", "ocr2"], 2)
    assert [v.source for v in r.votes] == ["ocr:apple", "reader:fake-model", "ocr:rapidocr"]
    eyes.second = None
    eyes.models["third"] = " Fake-Model "                  # the second's own model, case and spacing aside: no vote
    g = eyes.frame("00021_down.png")
    eyes.see(g, "Lo", box=CAROUSEL.box)
    s = reading.read(g, CAROUSEL, "label", "proof", choices=labels)
    assert s.refused.startswith(reading.DISAGREE) and not any(a.startswith("third") for a in eyes.asked)
    eyes.models["third"] = "other-model"
    eyes.answer("option", {"selected": "Lo"}, role="third")
    h = eyes.frame("00022_down.png")
    eyes.see(h, "Lo", box=CAROUSEL.box)
    t = reading.read(h, CAROUSEL, "label", "proof", choices=labels)
    assert (t.text, t.by, t.agreed, t.raw["third"]) == ("Lo", "votes", ["ocr", "third"], "Lo")
    assert eyes.asked[-1] == "third option" and t.votes[-1].source == "reader:other-model"


def test_an_ocr_reading_that_names_no_option_is_never_settled_by_the_reader_alone(eyes):
    """Where OCR read something that names no option, the reader's option does not stand alone: on the a1 II's proofs
    it was now and then another option (a neighbouring row, a button), where OCR had read nothing never."""
    f = eyes.frame("00018_down.png")
    eyes.see(f, "Fixed Speed Ric", box=CAROUSEL.box)
    eyes.answer("option", {"selected": "Fixed Speed REC"})
    r = reading.read(f, CAROUSEL, "label", "proof", choices=["Fixed Speed REC", "Fixed Speed STBY"])
    assert r.refused == f"{reading.DISAGREE}: ocr 'Fixed Speed Ric', reader 'Fixed Speed REC'"
    assert (r.by, r.choice, r.raw["reader"]) == ("none", None, "Fixed Speed REC")


def test_with_the_reader_down_a_plain_reading_goes_on_and_a_doubt_is_refused(eyes):
    eyes.answer("option", urllib.error.URLError("connection refused"))
    plain = eyes.frame("00007_right.png")
    eyes.see(plain, "Golden Ratio Grid", box=CAROUSEL.box)
    r = reading.read(plain, CAROUSEL, "label", "proof", choices=["Off", "Golden Ratio Grid"])
    assert (r.by, r.refused, r.raw["reader"]) == ("ocr", "", None)
    doubt = eyes.frame("00008_right.png")
    eyes.see(doubt, f"{CYR_ES_CAP}.Temp./Filter", box=CAROUSEL.box)
    d = reading.read(doubt, CAROUSEL, "label", "find", choices=["Auto", "C.Temp./Filter"])
    assert d.refused.startswith("reader needed: lookalike: CYRILLIC CAPITAL LETTER ES (the reader failed (URLError")
    assert (d.by, d.choice) == ("ocr", None) and eyes.asked == ["option", "option"] and reading.reader_down()
    later = eyes.frame("00009_right.png")
    eyes.see(later, f"120{CYR_ER}", box=CAROUSEL.box)
    a = reading.read(later, CAROUSEL, "label", "find")
    assert eyes.asked == ["option", "option"] and "did not answer just before" in a.refused
    # a site's own check never stands in for the reader (a reader is required): still refused
    b = reading.read(doubt, CAROUSEL, "label", "find", choices=["Auto", "C.Temp./Filter"], second="C.Temp./Filter")
    assert b.refused.startswith("reader needed") and (b.choice, "second" in b.raw) == (None, False)


def test_a_prompt_that_is_no_question_raises_and_trips_no_latch(eyes):
    f = eyes.frame("00019_right.png")
    with pytest.raises(KeyError):
        reading.ask(f, "optoin")
    with pytest.raises(KeyError):
        reading.ask(f, "optoin")
    assert not reading.reader_down() and eyes.asked == []


def test_the_reader_is_never_asked_about_a_black_frame(eyes):
    f = eyes.frame("00010_right.png", dark=True)
    eyes.answer("option", {"selected": "Auto"})
    r = reading.read(f, CAROUSEL, "label", "proof", choices=["Auto", "Manual"])
    assert eyes.asked == [] and r.refused.startswith("reader needed: empty") and "black frame" in r.refused


def test_the_lit_item_is_read_inside_the_cursor_and_nothing_lit_is_said(eyes):
    f = eyes.frame("00011_down.png", bar=(140, 212, 560, 252))
    eyes.see(f, "Shutter Type", box=(150, 215, 400, 250))
    eyes.see(f, "Silent Shooting", box=(150, 255, 400, 290))          # another row: not lit
    r = reading.read(f, reading.LIT, "label", "note")
    assert (r.text, r.by, r.refused, eyes.asked) == ("Shutter Type", "ocr", "", [])
    n = reading.read(eyes.frame("00012_down.png"), reading.LIT, "label", "note")
    assert (n.by, n.refused, n.choice, eyes.asked) == ("none", "nothing is lit", None, [])


ICON_LEFT_OUT = [
    # (OCR's reading of a row, the rows on the page, what finding a row takes it for, or None: judged as read)
    ("SAF Frame Move Amt", ["AF Frame Move Amt", "AF Area"], "AF Frame Move Amt"),       # an icon glued in front
    ("& Priority Set in AWB", ["Priority Set in AWB", "White Balance"], "Priority Set in AWB"),
    ("v dFor viewfinder", ["For viewfinder", "Monitor Off"], "For viewfinder"),    # two characters, spacing aside
    (f"{I_CIRCUMFLEX} Fixed Speed STBY", ["Fixed Speed STBY", "Fixed Speed REC"], "Fixed Speed STBY"),
    ("Tv Auto/Manual Switch", ["Av Auto/Manual Switch"], None),    # a short first word tells two rows apart
    ("Tv Auto/Manual Switch", ["Av Auto/Manual Switch", "Tv Auto/Manual Switch"], None),   # named as read
    ("10Sec", ["0Sec", "5 Sec"], None),                            # never a digit left out, nor one before a digit
    ("S Off", ["Off", "On"], None),                                # what is left is too short to be plain
    ("uir Rear Dial R", ["Rear Dial R", "Rear Dial L"], None),     # three letters: page_model.same_text's limit too
    ("SAF Frame", ["AF Frame", "SAF Frames"], None),               # it names another row loosely as read
    ("SAF Frame Move Amt", [], None),                              # no rows to name
]


def test_finding_a_row_leaves_out_the_icon_ocr_read_in_front_of_its_label():
    """Most menu rows OCR reads with their icon in front read "loose" (the census): finding a row leaves the icon out
    first, as page_model.same_text does, where what is left names one row exactly; only the reading loses its front,
    never a row's label, so "Tv" and "Av" rows stay apart."""
    for text, rows, want in ICON_LEFT_OUT:
        assert reading.icon_left_out(text, rows) == want, (text, rows)
        found = doubts(text, "label", choices=rows, find=True)
        if want is not None:
            assert found == [] and doubts(text, "label", choices=rows) != [], text
        else:
            assert found == doubts(text, "label", choices=rows), text
    assert reading.without_icon("& Priority Set in AWB") == "Priority Set in AWB"
    assert doubts("SAF Frame Move Amt", "number", choices=["AF Frame Move Amt"], find=True) != []   # labels only


def test_read_finds_a_row_without_the_icon_and_keeps_the_label(eyes):
    f = eyes.frame("00014_down.png", bar=(140, 212, 560, 252))
    eyes.see(f, "SAF Frame Move Amt", box=(150, 215, 400, 250))
    rows = ["AF Frame Move Amt", "AF Area", "Focus Area"]
    assert doubts("SAF Frame Move Amt", "label", choices=rows) == ["loose"]     # as read, it names no row exactly
    r = reading.read(f, reading.LIT, "label", "find", choices=rows)
    assert (r.text, r.choice, r.by, r.refused, r.doubts, eyes.asked) == ("AF Frame Move Amt", 0, "ocr", "", [], [])
    assert r.raw["ocr"] == "SAF Frame Move Amt"                     # the reading as read stays the evidence
    # OCR votes with what it judged, so the vote that made the reading is one that agrees with it (census and read()
    # run the one rule)
    assert (r.agreed, [(v.eye, v.text) for v in r.votes]) == (["ocr"], [("ocr", "AF Frame Move Amt")])
    assert r.evidence()["ocr"] == "SAF Frame Move Amt" and r.independent() == 1
    eyes.answer("option", {"selected": "AF Frame Move Amt"})
    p = reading.read(f, reading.LIT, "label", "proof", choices=rows)  # a proof judges it as read, and asks
    assert (p.doubts, p.by, p.choice, eyes.asked) == (["loose"], "both", 0, ["option"])


OLD_PROMPTS = {"dialog": "1b3b30c7a27da116", "menu": "e2882d49e3ecef0d", "notice": "c362fb838cf2f179",
               "option": "6bd26e33cfdc9f59", "fields": "6dbde91f9090b179", "any": "dd3babc8f5e633f7"}


def test_each_kind_of_screen_has_a_question_of_its_own_beside_the_old_ones():
    """The old questions keep their text (the answers already cached are keyed by it, and every caller asks them); each
    kind of screen's new question is a key of its own and asks for its field in one pinned JSON line, in plain ASCII;
    those that read a lit item that may be missing say to answer "none" then. A region of a field that holds no one
    reading (a checklist's boxes, a number-entry screen's boxes without k) is refused, where a pick would give a
    list's text."""
    import hashlib

    from camkit import vlm
    for key, digest in OLD_PROMPTS.items():
        assert hashlib.sha1(vlm.PROMPTS[key].encode()).hexdigest()[:16] == digest, key
    for kind, q in reading.QUESTIONS.items():
        text = vlm.PROMPTS[q.prompt]
        assert q.prompt.endswith(".v2") and q.prompt not in OLD_PROMPTS, kind
        assert text.isascii() and "Reply with JSON only, on one line: {" in text and f'"{q.field}"' in text, kind
        assert q.expect in reading.EXPECTS and len(text) < 600, kind
    assert [k for k, v in vlm.PROMPTS.items() if k.endswith(".v2") and "write none" in v] == \
        ["lit.v2", "cell.v2", "stars.v2"]
    assert reading.region("number field", k=1).pick({"fields": ["5", "6"]}) == "6"
    assert reading.region("carousel").box == CAROUSEL.box and reading.region("list").box is None
    assert reading.region("wb grid", field="G-M").pick({"A-B": "A7", "G-M": "M1.5"}) == "M1.5"
    with pytest.raises(KeyError):
        reading.region("no such kind")
    for kind, k in (("checklist", None), ("checklist", 0), ("number field", None)):
        with pytest.raises(ValueError):
            reading.region(kind, k=k)


# what reads through the new questions, and the tool that measures them: nowhere else in the kit until a caller is
# switched, kind by kind (docs/REMAPPING_PLAYBOOK.md, section 5)
NEW_QUESTION_NAMES = re.compile(r'\.v2["\']|\bicon_left_out\(|\bwithout_icon\(|\bfind=True\b|\breading\.region\(|\bQUESTIONS\b|\bask_named_reader\(|\bwith_options\('
                                r'|\breading\.read\(')
MAY_NAME_THEM = {"kit/camkit/reading.py", "kit/camkit/vlm.py", "kit/tools/reader_census.py"}


def test_no_caller_asks_the_new_questions_or_reads_by_the_rule_yet():
    """Every caller still asks the questions it asked before 2026-11-13: none names a ".v2" question, QUESTIONS,
    reading.region, reading.read, vlm.with_options or vlm.ask_named_reader (provers/pp_reset_run.py's own ask_reader is
    another function, asking the old questions)."""
    found = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "kit").rglob("*.py")
                   if "tests" not in p.parts and "__pycache__" not in p.parts
                   and p.relative_to(ROOT).as_posix() not in MAY_NAME_THEM
                   and NEW_QUESTION_NAMES.search(p.read_text(encoding="utf-8")))
    assert found == [], f"these name the new questions or read through camkit.reading.read: {found}"


def test_read_asks_a_kinds_own_question_when_given_its_region(eyes):
    f = eyes.frame("00015_right.png")
    eyes.see(f, "1/25", box=CAROUSEL.box)
    eyes.answer("carousel.v2", {"selected": "1/250"})
    r = reading.read(f, reading.region("carousel"), "number", "proof", choices=["1/25", "1/250"])
    assert eyes.asked == ["carousel.v2"] and r.raw["reader"] == "1/250"


def test_the_options_are_handed_to_the_reader_before_its_json_line():
    from camkit import vlm
    q = vlm.with_options(vlm.PROMPTS["lit.v2"], ["Off", f"Add Rating ({STAR})"])
    assert q.index("one of these") < q.index("Reply with JSON only") and f'"Add Rating ({STAR})"' in q
    assert q.startswith(vlm.PROMPTS["lit.v2"].split("Reply with JSON")[0])
    boxes = vlm.with_options(vlm.PROMPTS["fields.v2"], {"box 1": ["5", "6"], "box 2": []})
    assert 'The box 1 should be one of these: "5", "6".' in boxes and "box 2" not in boxes


def test_note_takes_ocr_alone_whatever_its_doubts(eyes):
    f = eyes.frame("00013_down.png")
    eyes.see(f, f"120{CYR_ER}", box=CAROUSEL.box)
    eyes.answer("option", {"selected": "120p"})
    r = reading.read(f, CAROUSEL, "label", "note")
    assert (r.text, r.by, r.refused, eyes.asked) == ("120p", "ocr", "", [])


def test_a_guard_refuses_a_doubt_without_the_readers_answer_and_a_lone_reader(eyes):
    """A guard keeps every eye's reading for its own judgement (texts, the raw beside the canonical) and refuses what
    no eye can read, a doubt the reader does not answer, and a lone reader's reading unless a second, independent
    vote names the same; a vote that settles a disagreement never takes away a refusal of the guard's own."""
    bar, row = (140, 212, 560, 252), (150, 215, 400, 250)
    f = eyes.frame("00014_down.png", bar=bar)                          # OCR reads nothing in the bar
    eyes.answer("menu", {"rows": [{"label": "Format", "highlighted": True}, {"label": "Movie", "highlighted": False}]})
    r = reading.read(f, reading.LIT_ROW, "label", "guard")
    assert (r.by, r.refused, r.texts(), eyes.asked) == ("reader", "one reader's reading never clears a guard alone",
                                                        ["Format"], ["menu"])
    assert safety.never_open(r.texts()[0])                 # the caller's guard still judges what was read
    eyes.second = "rapidocr"
    g = eyes.frame("00023_down.png", bar=bar)
    eyes.see(g, "Format", box=row, eng="rapidocr")
    s = reading.read(g, reading.LIT_ROW, "label", "guard")
    assert (s.by, s.refused, s.agreed) == ("votes", "", ["ocr2", "reader"]) and "Format" in s.texts()
    eyes.answer("menu", {"rows": []})
    eyes.second = None
    n = reading.read(eyes.frame("00015_down.png", bar=bar), reading.LIT_ROW, "label", "guard")
    assert (n.refused, n.texts()) == ("nothing could be read there: a guard cannot judge it", [])
    eyes.second = "rapidocr"
    h = eyes.frame("00016_down.png", bar=bar)
    eyes.see(h, f"F{CYR_O}rmat", box=row)
    eyes.see(h, "Format", box=row, eng="rapidocr")
    k = reading.read(h, reading.LIT_ROW, "label", "guard")
    assert k.refused.startswith("reader needed: lookalike: CYRILLIC SMALL LETTER O") and k.choice is None
    assert k.texts() == [f"F{CYR_O}rmat", "Format"] and k.raw["ocr2"] == "Format"



def test_a_guard_refuses_any_two_eyes_that_read_differently_and_no_vote_settles_it(eyes):
    """A third vote never outvotes a refusal: OCR reads "Format" (with a Cyrillic o), the reader and the second OCR
    engine "Movie". Two of three name Movie, and the guard still refuses: it may only add refusals, and every reading
    goes to its own judgement. Nor does a guard ask the third reader for anything but a lone reader's reading."""
    bar, row = (140, 212, 560, 252), (150, 215, 400, 250)
    eyes.second = "rapidocr"
    eyes.models["third"] = "other-model"
    eyes.answer("menu", {"rows": [{"label": "Movie", "highlighted": True}]})
    f = eyes.frame("00060_down.png", bar=bar)
    eyes.see(f, f"F{CYR_O}rmat", box=row)
    eyes.see(f, "Movie", box=row, eng="rapidocr")
    r = reading.read(f, reading.LIT_ROW, "label", "guard")
    assert r.refused.startswith(reading.DISAGREE) and (r.choice, r.agreed) == (None, [])
    assert r.texts() == [f"F{CYR_O}rmat", "Format", "Movie"] and safety.never_open(r.texts()[0])
    assert not any(a.startswith("third") for a in eyes.asked)


def test_a_guard_is_never_read_again_for_a_better_answer_and_every_frames_reading_is_kept(eyes):
    """With fresh frames to spare, a guard refuses on the frame that read apart: a later frame read plainly would drop
    the never-open reading it saw. Whatever the stakes, every frame's readings stay for the judging (texts)."""
    bar, row = (140, 212, 560, 252), (150, 215, 400, 250)
    eyes.answer("menu", {"rows": [{"label": "Movie", "highlighted": True}]})
    eyes.answer("option", {"selected": "Movie"})
    frames = [eyes.frame(f"0007{n}_down.png", bar=bar) for n in range(4)]
    for f, said in zip(frames, (f"F{CYR_O}rmat", "Movie") * 2, strict=True):
        eyes.see(f, said, box=row)
    grab = iter(frames).__next__
    r = reading.read(grab, reading.LIT_ROW, "label", "guard", fresh=1)
    assert r.refused.startswith(reading.DISAGREE) and r.frame == "00070_down.png" and "Format" in r.texts()
    assert grab() is frames[1]                             # the guard grabbed no fresh frame
    p = reading.read(iter(frames[2:]).__next__, reading.LIT, "label", "proof", choices=["Format", "Movie"], fresh=1)
    assert (p.text, p.by, p.frame) == ("Movie", "both", "00073_down.png")
    assert f"F{CYR_O}rmat" in p.texts() and "Format" in p.texts()        # frame 1's reading kept

def test_a_refused_reading_never_names_an_option(eyes):
    """A caller that looked at .choice first must find none on a refused reading, whatever refused it."""
    labels = ["Lo", "Mid", "Hi"]
    eyes.answer("option", {"selected": "Hi"})
    cases = []
    f = eyes.frame("00030_down.png")
    eyes.see(f, "Lo", box=CAROUSEL.box)
    cases.append(reading.read(f, CAROUSEL, "label", "proof", choices=labels))          # readers apart
    cases.append(reading.read(eyes.frame("00031_down.png"), CAROUSEL, "label", "press", choices=labels))   # lone
    eyes.answer("option", urllib.error.URLError("refused"))
    g = eyes.frame("00032_down.png")
    eyes.see(g, "Hi", box=CAROUSEL.box)
    cases.append(reading.read(g, CAROUSEL, "label", "find", choices=labels))           # reader needed
    cases.append(reading.read(g, CAROUSEL, "label", "guard", choices=labels))          # a guard's reader needed
    assert all(c.refused and c.choice is None and c.agreed == [] for c in cases), [c.refused for c in cases]


def test_read_takes_only_the_stakes_and_kinds_it_knows(eyes):
    f = eyes.frame("00017_down.png")
    with pytest.raises(ValueError):
        reading.read(f, CAROUSEL, "label", "maybe")
    with pytest.raises(ValueError):
        reading.read(f, CAROUSEL, "word", "find")


# ---------------------------------------------------------------------------------------------- who reads by themselves

# Modules that read the screen by themselves: OCR (camkit.ocr.read, runner.read_frames) or a reader (camkit.vlm.ask_role,
# proving.screens.ask_second, a reader built by camkit.vlm.make_reader) called directly, not through camkit.reading. A
# module moved onto camkit.reading leaves this list, and none joins it: it only gets shorter (docs/decisions/0022).
READ_BY_THEMSELVES = [
    "kit/camkit/live.py", "kit/crawl_run.py", "kit/drive.py", "kit/help_reads.py", "kit/help_run.py",
    "kit/page_model.py", "kit/pass1_labels.py", "kit/prove_run.py",
    "kit/provers/afreg_run.py", "kit/provers/boxes_run.py", "kit/provers/bracket_run.py",
    "kit/provers/customshoot_run.py", "kit/provers/filter_run.py", "kit/provers/grid_run.py",
    "kit/provers/mode_switch.py", "kit/provers/mymenu_run.py", "kit/provers/orient_run.py",
    "kit/provers/pp_reset_run.py", "kit/provers/scale_run.py", "kit/provers/shootmode_run.py",
    "kit/proving/checklists.py", "kit/proving/fields.py", "kit/proving/looks.py", "kit/proving/nav.py",
    "kit/proving/options.py", "kit/proving/screens.py", "kit/proving/sidelists.py", "kit/proving/tables.py",
    "kit/proving/wbgrid.py", "kit/runner.py", "kit/table_walk.py", "kit/tiebreak.py", "kit/tools/hdmi_watch.py",
    "kit/tools/help_extras.py", "kit/tools/ocr_compare.py", "kit/tools/reread_proofs.py", "kit/tools/selftest.py",
]
SEAMS = {"kit/camkit/ocr.py", "kit/camkit/vlm.py", "kit/camkit/reading.py"}
DIRECT = re.compile(r"\bocr\.read\(|\bask_role\(|\bask_second\(|\bmake_reader\(|\bread_frames\(")


def test_the_modules_that_read_the_screen_by_themselves_only_get_fewer():
    found = {p.relative_to(ROOT).as_posix() for p in (ROOT / "kit").rglob("*.py")
             if "tests" not in p.parts and "__pycache__" not in p.parts}
    found = sorted(p for p in found - SEAMS if DIRECT.search((ROOT / p).read_text(encoding="utf-8")))
    new, gone = sorted(set(found) - set(READ_BY_THEMSELVES)), sorted(set(READ_BY_THEMSELVES) - set(found))
    assert not new, f"these read the screen by themselves: read it through camkit.reading.read instead: {new}"
    assert not gone, f"these no longer read the screen by themselves: take them off READ_BY_THEMSELVES: {gone}"


# ---------------------------------------------------------------------------------------------- kit/tools/reader_census.py

def census_run(tmp_path) -> Path:
    """A made-up camera's run root with one run: proofs (made-up labels, one reading glued to a made-up owner's word)
    and a page model whose rows carry values, one row read apart by OCR and the reader and settled by the second OCR
    engine."""
    root = tmp_path / "TEST-CAM_fw9.99"
    run = root / "kit2_pass2"
    (run / "shots").mkdir(parents=True)
    proofs = [
        {"path": ["White Balance"], "kind": "dialog", "index": 0, "label": "C.Temp./Filter",
         "shown": f"{CYR_ES_CAP}.Temp./Filter", "vlm": "C.Temp./Filter", "chosen_frame": "00001.png"},
        {"path": ["White Balance"], "kind": "dialog", "index": 1, "label": "Auto", "shown": "Auto Mode",
         "chosen_frame": "00002.png"},
        {"path": ["Black Level"], "kind": "sidelist", "index": 0, "label": "-15", "shown": "", "chosen_frame": "00003.png"},
        {"path": ["Black Level"], "kind": "sidelist", "index": 1, "label": "+15", "shown": "+15", "chosen_frame": "00004.png"},
        {"path": ["Recog. Target"], "kind": "checklist", "index": 0, "label": "Eye", "chosen_frame": "00005.png"},
        {"path": ["Ownerish"], "kind": "list", "index": 0, "label": "Zqx Option", "shown": "Zqx Secretvalue",
         "vlm": "Zqx Option", "chosen_frame": "00006.png"},
    ]
    (run / "proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in proofs), encoding="utf-8")
    (run / "readings.jsonl").write_text(json.dumps({"frame": "00003.png", "reading": "-15"}) + "\n", encoding="utf-8")
    pages = [{"page": "1/3", "rows": [
        {"label": "Format", "readings": {"label": {"ocr": f"F{CYR_O}rmat", "vllm": "Format"}, "value": {"ocr": "OWNERVALUE"}}},
        {"label": "Drive Mode", "readings": {"label": {"ocr": "Drive Mode"}, "value": {"ocr": "OWNERVALUE"}}},
        {"label": "Shutter Type", "readings": {"label": {"ocr": "Shutter Tape", "ocr2": "Shutter Type",
                                                         "vllm": "Shutter Type"}}}]}]
    (run / "model.json").write_text(json.dumps(pages), encoding="utf-8")
    return root


def files_of(top: Path) -> dict:
    return {p: (p.stat().st_size, p.stat().st_mtime_ns) for p in top.rglob("*")}


def test_the_census_judges_each_box_of_a_number_entry_proof_apart():
    """kit/proving/fields.py keeps a number-entry screen's boxes as one reading joined by " | ", as its label: the
    census judges each box against that box's values on the row, never the joined text, whose bars the thin-stroke
    rule would read as ones."""
    import reader_census
    line = {"kind": "fields", "label": "5 | 6 | 0", "shown": "5 | 8 | 0"}
    rows = ["4 | 6 | 0", "5 | 6 | 0", "5 | 7 | 0"]
    assert reader_census.boxes_of(line, line["shown"], None, None, rows) == [
        ("5", "5", None, None, ["4", "5"]), ("8", "6", None, None, ["6", "7"]), ("0", "0", None, None, ["0"])]
    assert reader_census.boxes_of({"kind": "list", "label": "Off"}, "Off", "Off", None, ["Off", "On"]) == [
        ("Off", "Off", "Off", None, ["Off", "On"])]


def test_the_census_counts_without_a_reader_and_prints_no_reading(tmp_path, capsys):
    import reader_census
    root = census_run(tmp_path)
    before = files_of(root)
    assert reader_census.main([str(root), "--json"]) == 0
    out = capsys.readouterr().out
    got = json.loads(out)
    p, m = got["proofs"], got["menus"]
    assert got["runs"] == 1 and p["counts"]["proof lines"] == 6 and p["counts"]["no OCR reading kept"] == 1
    assert p["counts"]["read"] == 5 and p["readers"] == {"own": 2, "none": 2, "readings.jsonl": 1}
    assert p["doubts"] == {"no option": 2, "lookalike": 1, "empty": 1, "short": 1}
    assert p["letters"] == {"lookalike: CYRILLIC CAPITAL LETTER ES": 1}
    assert p["outcomes"] == {"reader needed": 2, "stands on both": 1, "stands on one reader": 1, "ocr names no option": 1}
    assert p["counts"]["extra reader calls"] == 2 and "with a second OCR engine's reading" not in p["counts"]
    assert p["third vote"] == {"apart, no second OCR engine's reading kept": 1}
    assert m["counts"]["read"] == 3 and m["sites"]["menu row"] == {"read": 3, "plain": 1, "doubtful": 2}
    assert m["third vote"] == {"apart, settled by the second OCR engine: names the label": 1}
    assert reader_census.main([str(root / "kit2_pass2")]) == 0
    text = capsys.readouterr().out
    assert "no proof line keeps a second OCR engine's reading" in text
    for said in ("Secretvalue", "OWNERVALUE", "Zqx", "Temp", "Format", "Black Level", "Shutter"):
        assert said not in out and said not in text, said
    assert files_of(root) == before                        # the runs are only read


def test_the_census_asks_the_reader_only_when_told_and_keeps_no_answer_in_the_runs(tmp_path, eyes, monkeypatch, capsys):
    import numpy as np
    import reader_census
    from camkit import vlm
    from PIL import Image
    root = census_run(tmp_path)
    Image.fromarray(np.full((480, 640, 3), 90, np.uint8)).save(root / "kit2_pass2" / "shots" / "00004.png")
    monkeypatch.setattr(vlm, "config", lambda: {"readers": [{"name": "fake reader", "url": "http://127.0.0.1:9/v1",
                                                              "model": "m"}]})
    monkeypatch.setattr(vlm, "CACHE", None)
    # what the kit says on the way (a reader standing in) must not reach the JSON on standard output
    eyes.answer("option", lambda image: print("reader 'fake' does not answer: 'other' stands in") or {"selected": "+15"})
    before = files_of(root)
    assert reader_census.main([str(root), "--json"]) == 0 and eyes.asked == []
    capsys.readouterr()
    assert reader_census.main([str(root), "--json", "--ask", "--cache", str(tmp_path / "answers")]) == 0
    said = capsys.readouterr()
    got = json.loads(said.out)
    assert "stands in" in said.err and eyes.asked == ["option"] and got["asked"] == {"frames": 1, "answered": 1}
    assert got["proofs"]["readers"]["asked"] == 1 and Path(vlm.CACHE) == tmp_path / "answers"
    assert files_of(root) == before
    with pytest.raises(SystemExit):
        reader_census.main([str(root), "--limit", "3"])


# ---------------------------------------------------------------------------------------------- reader_census.py --questions

Q_ANSWERS = {
    # frame: (a marker the options question holds and the decoy question leaves out, {question: the fake's answer})
    "00001.png": ('"Zqx Alpha"', {"option": {"selected": "Zqx Alpha"}, "new": {"selected": "Zqx Alpha"},
                                  "decoy": {"selected": "Zqx Beta"}}),
    "00002.png": ('"Zqx Beta"', {"option": {"selected": "Mode"}, "new": {"selected": "Zqx Beta"}}),
    "00003.png": ('"Zqx Gamma"', {"option": {"selected": "Zqx Beta"}, "new": {"selected": "Zqx Gamma"}}),
    "00004.png": ('"5"', {"option": {"selected": "Minimum"}, "fields": {"fields": ["5", "6"], "active": 0},
                          "new": {"fields": ["5", "6"], "active": 0}, "decoy": {"fields": ["7", "6"], "active": 0}}),
    "00005.png": ('"7"', {"option": {"selected": "7"}, "fields": {"fields": ["7", "6"], "active": 0},
                          "new": {"fields": ["7 sec", "6"], "active": 0}}),
    "00006.png": ('"A7"', {"option": {"selected": "Auto"}, "new": {"A-B": "A7", "G-M": "0"}}),
    "00007.png": ('"B7"', {"option": {"selected": "Auto"}, "new": {"A-B": "B 7", "G-M": "0"}}),
    "00008.png": ("", {"option": {"selected": "Enter"},
                       "new": {"boxes": [{"label": "Zqx One", "ticked": False}, {"label": "Zqx Two", "ticked": True}]}}),
}


def questions_run(tmp_path) -> Path:
    """A made-up camera's run root with proofs of four kinds (made-up labels), a picture of its own for each frame and
    one black frame."""
    import numpy as np
    from PIL import Image
    root = tmp_path / "TEST-CAM_fw9.99"
    run = root / "kit2_pass2"
    (run / "shots").mkdir(parents=True)
    proofs = [
        {"path": ["Zqx Mode"], "kind": "list", "label": "Zqx Alpha", "shown": "Zqx Alpha", "vlm": "Zqx Alpha",
         "chosen_frame": "00001.png"},
        {"path": ["Zqx Mode"], "kind": "list", "label": "Zqx Beta", "shown": "Zqx Beta", "vlm": "Mode",
         "chosen_frame": "00002.png"},
        {"path": ["Zqx Mode"], "kind": "list", "label": "Zqx Gamma", "shown": "Zqx Gamma", "chosen_frame": "00003.png"},
        {"path": ["Zqx Mode"], "kind": "list", "label": "Zqx Delta", "shown": "", "chosen_frame": "00009.png"},
        {"path": ["Zqx Level"], "kind": "fields", "label": "5 | 6", "shown": "5 | 6", "value": "5", "vlm": "Minimum",
         "chosen_frame": "00004.png"},
        {"path": ["Zqx Level"], "kind": "fields", "label": "7 | 6", "shown": "7 | 6", "value": "7",
         "chosen_frame": "00005.png"},
        {"path": ["White Balance"], "kind": "wbgrid", "option": "grid 0", "axis": "A-B", "label": "Auto A-B -7000",
         "value": -7000, "vlm": "Auto", "chosen_frame": "00006.png"},
        {"path": ["White Balance"], "kind": "wbgrid", "option": "grid 0", "axis": "A-B", "label": "Auto A-B 7000",
         "value": 7000, "chosen_frame": "00007.png"},
        {"path": ["Zqx Set"], "kind": "checklist", "label": "Zqx Two", "vlm": "Enter", "chosen_frame": "00008.png",
         "boxes": [{"box": 0, "label": "Zqx One", "ticked": False}, {"box": 1, "label": "Zqx Two", "ticked": True}]},
    ]
    (run / "proofs.jsonl").write_text("".join(json.dumps(p) + "\n" for p in proofs), encoding="utf-8")
    for n in range(1, 10):
        level = 0 if n == 9 else 60 + n
        Image.fromarray(np.full((480, 640, 3), level, np.uint8)).save(run / "shots" / f"{n:05d}.png")
    return root


class QuestionsReader:
    """A reader faked for the census's --questions: its answer by the frame and the question (Q_ANSWERS)."""

    def __init__(self, shots: Path, asked: list):
        self.by_bytes = {p.read_bytes(): p.name for p in shots.glob("*.png")}
        self.asked = asked

    def answer(self, image: bytes, prompt: str, waits=None):
        from camkit import vlm
        name = self.by_bytes[image]
        marker, said = Q_ANSWERS[name]
        which = ("option" if prompt == vlm.PROMPTS["option"] else "fields" if prompt == vlm.PROMPTS["fields"]
                 else "decoy" if "one of these" in prompt and marker not in prompt and "decoy" in said else "new")
        self.asked.append((name, which))
        return said.get(which) or said["new"]


def test_the_census_measures_each_kinds_questions_against_the_option_proved(tmp_path, monkeypatch, capsys):
    import reader_census
    from camkit import vlm
    root = questions_run(tmp_path)
    asked = []
    monkeypatch.setattr(vlm, "config", lambda: {"readers": [{"name": "fake", "url": "http://127.0.0.1:9/v1",
                                                              "model": "m", "parallel": 2}]})
    monkeypatch.setattr(vlm, "CACHE", None)
    monkeypatch.setattr(vlm, "make_reader", lambda cfg, **kw: QuestionsReader(root / "kit2_pass2" / "shots", asked))
    before = files_of(root)
    answers = tmp_path / "answers"
    assert reader_census.main([str(root), "--questions", "--json", "--cache", str(answers)]) == 0
    got = json.loads(capsys.readouterr().out)
    s = got["scores"]
    assert got["readers"] == ["fake"] and got["black frames left out"] == 1
    assert s["list"]["old: option"]["fake"] == {"right": 1, "no option": 1, "another option": 1}
    assert s["list"]["new"]["fake"] == {"right": 3} and s["list"]["new + options"]["fake"] == {"right": 3}
    assert s["list"]["new + decoy"]["fake"] == {"right": 2, "another option": 1}     # the list's pick: a wrong one
    # a number-entry screen: the box the proof changed, which its file proved (the others are as the run planned them)
    assert s["number field"]["old: option"]["fake"] == {"no option": 1, "right": 1}
    assert s["number field"]["old: fields"]["fake"] == {"right": 2} == s["number field"]["new"]["fake"]
    assert s["number field"]["new + decoy"]["fake"] == {"right": 1, "another option": 1}
    assert s["wb grid"]["old: option"]["fake"] == {"no option": 2} and s["wb grid"]["new"]["fake"] == {"right": 2}
    assert s["checklist"]["old: option"]["fake"] == {"no option": 1} and s["checklist"]["new"]["fake"] == {"right": 1}
    assert got["sampled"]["list"] == {"frames": 3, "items": 3, "agreed": 1, "apart": 1, "none": 1}
    assert got["asked"]["fake"]["asked"] == len(asked) and "00009.png" not in {n for n, _ in asked}
    assert files_of(root) == before and any(answers.iterdir())          # the runs only read, the answers kept apart
    asked.clear()
    assert reader_census.main([str(root), "--questions", "--minutes", "0", "--cache", str(answers)]) == 0
    text = capsys.readouterr().out
    assert asked == [] and "from a cache" in text                      # --minutes 0: the caches alone
    for said in ("Zqx", "Minimum", "Auto", "Enter", "00001", ".png"):
        assert said not in text, said
    with pytest.raises(SystemExit):
        reader_census.main([str(root), "--questions", "--reader", "nobody"])
    with pytest.raises(SystemExit):
        reader_census.main([str(root), "--questions", "--kinds", "no such kind"])
    with pytest.raises(SystemExit):
        reader_census.main([str(root), "--reader", "fake"])                # --reader goes with --questions


def test_the_census_judges_each_answer_by_its_kind_of_screen():
    import reader_census as rc
    assert [rc.number_of(t) for t in ("ISO 2500", f"{PLUS_MINUS}0", "-0", "+9", "02", "1,5 sec", "Minimum")] == \
        ["2500", "0", "0", "9", "2", "1.5", None]
    assert [rc.star_count(t) for t in (STAR * 3, "2", "4 stars", "**", "off", "none")] == [3, 2, 4, 2, 0, None]
    assert [rc.wb_value("A-B", t) for t in ("A7", "B 0.5", "A-B: A7", "0", "G2")] == [-7000, 500, -7000, 0, None]
    assert rc.wb_readout("G-M", 1250) == "M1.25" and rc.wb_readout("A-B", -7000) == "A7"
    base = rc.Item("look base", Path("f.png"), "PT", ["ST", "PT", "NT"])
    assert [rc.judge(base, t) for t in ("PT (Portrait)", "PT(Portrait)", "NT", "Look")] == \
        ["right", "right", "another option", "no option"]
    pick = rc.Item("table picker", Path("f.png"), "& Priority Set in AWB", ["White Balance", "& Priority Set in AWB"],
                   extra={"expect": "label"})
    assert rc.judge(pick, "Priority Set in AWB") == "right" and rc.judge(pick, "AF/MF") == "no option"
    stars = rc.Item("star rating", Path("f.png"), 2, [1, 2, 3])
    assert [rc.judge(stars, t) for t in ("2", STAR, "none")] == ["right", "another option", "no option"]
    title = rc.Item("title", Path("f.png"), "Grid Line Type")
    assert [rc.judge(title, t) for t in ("Grid Line Type", "Grid Line", "none")] == ["right", "another option",
                                                                                     "no option"]
    note = rc.Item("notice", Path("f.png"), "The input value is invalid. Please verify and input again. OK")
    assert rc.judge(note, "The input value is invalid. Please verify and input again.") == "right"
    # a run's labels as OCR recorded them (an icon glued on, a letter lost, stars) against what a reader reads drawn
    assert rc.names("Rating Only (*****)", [f"Rating Only ({STAR * 4})", f"Rating Only ({STAR * 5})"], "label") == 1
    assert rc.names("Fixed Speed STBY", [f"{I_CIRCUMFLEX} Fixed Speed SBY", "Fixed Speed REC"], "label") == 0
    assert rc.names("Right 1/2", ["LRight 1/2", "Left 1/2"], "label") == 0
    assert rc.names("Fixed Speed", ["Fixed Speed STBY", "Fixed Speed REC"], "label") is None    # close to both
    assert rc.drawn_alike("LRight 1/2", ["LRight 1/2", "Right 1/2"]) and not rc.drawn_alike("+3", ["+3", "3"])
    assert reading.without_icon("+3 EV") == "+3 EV" and reading.without_icon("- 5") == "5"
    # only the reading loses an icon in front, never the label, and a label's short first word must be read too
    assert not rc.drawn_alike("AF On", ["AF On", "MF On"]) and not rc.drawn_alike("MF On", ["AF On", "MF On"])
    assert rc.names("Tv Auto/Manual Switch", ["Av Auto/Manual Switch"], "label") is None
    av = rc.Item("list", Path("f.png"), "Av Auto/Manual Switch", ["Av Auto/Manual Switch", "Off"],
                 extra={"expect": "label"})
    assert rc.judge(av, "Tv Auto/Manual Switch") == "no option" and rc.judge(av, "Av Auto/Manual Switch") == "right"
    assert rc.judge(rc.Item("title", Path("f.png"), "Av Auto/Manual Switch"), "Tv Auto/Manual Switch") == \
        "another option"
    rating = rc.Item("checklist", Path("f.png"), [(STAR * 2, True)], [STAR, STAR * 2], extra={"label": STAR * 2})
    assert rc.judge(rating, [{"label": "2", "ticked": True}, {"label": "1", "ticked": False}]) == "right"
    assert rc.judge(rating, [{"label": "2", "ticked": False}]) == "another option"
    assert rc.judge(rating, [{"label": "3", "ticked": True}]) == "no option"


class FailingReader:
    """A reader whose every question fails (a server short of memory: HTTP 507), counting the questions put to it."""

    def __init__(self, asked: list):
        self.asked = asked

    def answer(self, image: bytes, prompt: str, waits=None):
        self.asked.append(prompt)
        raise urllib.error.HTTPError("http://127.0.0.1:9/v1", 507, "Insufficient Storage", {}, None)


def census_config(monkeypatch, reader):
    from camkit import vlm
    monkeypatch.setattr(vlm, "config", lambda: {"readers": [{"name": "fake", "url": "http://127.0.0.1:9/v1",
                                                              "model": "m", "parallel": 1}]})
    monkeypatch.setattr(vlm, "CACHE", None)
    monkeypatch.setattr(vlm, "make_reader", lambda cfg, **kw: reader)


def test_a_readers_failures_are_its_own_and_stop_it_after_a_run_of_them(tmp_path, monkeypatch, capsys):
    """A reader that fails (HTTP 507, a timeout, a refusal, no JSON) is counted "reader failed", never a question's
    "no answer", and is left out of the right rate; after FAIL_RUN failures in a row it is asked nothing more ("not
    asked"), and the run says so once, rather than waiting out --minutes."""
    import reader_census
    root, asked = questions_run(tmp_path), []
    census_config(monkeypatch, FailingReader(asked))
    assert reader_census.main([str(root), "--questions", "--json", "--cache", str(tmp_path / "answers")]) == 0
    said = capsys.readouterr()
    got = json.loads(said.out)
    a = got["asked"]["fake"]
    assert a["failed"] == reader_census.FAIL_RUN == len(asked) and a["stopped after failures"] == 1
    assert a["not asked"] > 0 and "asked" not in a and "failed 8 questions in a row" in said.err
    every = collections_merge(got["scores"])
    assert set(every) == {"reader failed", "not asked"} and every["reader failed"] == reader_census.FAIL_RUN


def collections_merge(scores: dict) -> dict:
    out = {}
    for by_question in scores.values():
        for by_reader in by_question.values():
            for counts in by_reader.values():
                for k, v in counts.items():
                    out[k] = out.get(k, 0) + v
    return out


def test_once_time_is_up_nothing_is_asked_and_only_usable_answers_are_taken(tmp_path, monkeypatch, capsys):
    """--minutes 0 takes the answers already kept and asks nothing: an entry of the camera's own cache that is garbled
    ({"_unparsed": ...}) or cut short is no answer kept, so it is "not asked", never asked and never counted as from a
    cache."""
    import reader_census
    from camkit import vlm
    root, asked = questions_run(tmp_path), []
    census_config(monkeypatch, FailingReader(asked))
    image = (root / "kit2_pass2" / "shots" / "00001.png").read_bytes()
    own = root / "_cache" / "vlm"
    own.mkdir(parents=True)
    (own / f"{vlm.cache_key(image, vlm.PROMPTS['option'], 'm')}.json").write_text('{"_unparsed": "x"}', encoding="utf-8")
    (own / f"{vlm.cache_key(image, vlm.PROMPTS['lit.v2'], 'm')}.json").write_text('{"selected": "Zq', encoding="utf-8")
    (own / f"{vlm.cache_key(image, vlm.PROMPTS['fields'], 'm')}.json").write_text('{"fields": []}', encoding="utf-8")
    before = files_of(root)
    assert reader_census.main([str(root), "--questions", "--json", "--minutes", "0",
                               "--cache", str(tmp_path / "answers")]) == 0
    got = json.loads(capsys.readouterr().out)
    assert asked == [] and "from a cache" not in got["asked"]["fake"] and files_of(root) == before
    assert vlm.usable({"selected": "A"}) and not vlm.usable({"_unparsed": "x"}) and not vlm.usable({"_error": "x"})


def test_the_census_keeps_its_answers_outside_the_runs(tmp_path, monkeypatch, own_runs, capsys):
    import reader_census
    root = questions_run(tmp_path)
    census_config(monkeypatch, FailingReader([]))
    for inside in (root / "answers", root / "kit2_pass2" / "_cache", own_runs / "answers"):
        for mode in (["--questions"], ["--ask"]):
            with pytest.raises(SystemExit):
                reader_census.main([str(root), *mode, "--cache", str(inside)])
            assert not inside.exists()
    reader_census.main([str(root), "--minutes", "3", "--per-kind", "2"])
    assert "--per-kind, --minutes go with --questions" in capsys.readouterr().err


def test_the_census_samples_the_same_frames_every_time_a_smaller_sample_the_start_of_a_larger():
    import collections

    import reader_census as rc
    items = [rc.Item("list", Path(f"run/shots/{n:05d}.png"), "A", ["A", "B"], old="A" if n % 2 else "B",
                     extra={"expect": "label"}) for n in range(40)]
    small, large = rc.sample(items, 6)["list"], rc.sample(items, 20)["list"]
    assert [u[0].frame for u in small] == [u[0].frame for u in rc.sample(list(reversed(items)), 6)["list"]]
    assert {u[0].frame for u in small} <= {u[0].frame for u in large}
    assert collections.Counter(rc.old_split(u) for u in small) == {"agreed": 3, "apart": 3}
    dark = {small[0][0].frame}
    assert small[0][0].frame not in {u[0].frame for u in rc.sample(items, 6, lambda f: f not in dark)["list"]}


def test_the_menus_census_leaves_out_the_icon_before_judging_a_row():
    import reader_census
    t = reader_census.Tally()
    rows = ["AF Frame Move Amt", "AF Area"]
    assert t.add("menu row", "SAF Frame Move Amt", "AF Frame Move Amt", None, "label", rows, find=True) == "plain"
    assert t.add("menu row", "SAF Frame Move Amt", "AF Frame Move Amt", None, "label", rows) == "reader needed"
    assert t.c["icon left out"] == 1 and t.sites["menu row"]["plain"] == 1
