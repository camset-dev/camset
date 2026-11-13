"""Pass 2's proofs against the camera's definition: what the camera showed vs what the definition says.

    .venv/bin/python kit/pass2_report.py [kit2_pass2]          # a run in the camera's runs/<model>_fw<fw>/, or a path

Per proved row: the records its options changed and, per option, label -> value. Each row is
compared with the definition of the camera the kit works on, editor/definitions/<model>_fw<fw>.json (camkit.paths;
key "global:0x...", values [[value, label], ...]):
  agrees      every proved value has the schema's label for it (same text, ignoring case/spaces)
  wording     the same meaning worded another way ("Fixed" / "Fix")
  missing     the schema has the record but lacks a proved value, or its label is blank
  conflict    the schema gives a value the label of another proved option, or a label nothing like
              the camera's: the schema is wrong for that value, or the option was renamed
              ("Free Size" is "Custom" on firmware 4.00); each one is checked by eye
  new         the schema does not have the record
  linked      the option changed more than one record (copies, or a dependency: kept as found)
Values only: the camera's start values are never printed (generated docs never show the user's
own settings). Writes <run>/report.json.

    .venv/bin/python kit/pass2_report.py [RUN] [--no-schema] [--alone]

The main run (kit2_pass2, which kit/schema_update.py writes the definition from) is reported with the camera's other
proof runs, the run folders a prover marked as one (camkit.runs.PROOF_RUN: kit/provers/afreg_run.py's, filter_run.py
--run's; proof_runs): each run's attempts and failures say which of its own proofs count, each proof made in another run
names its files with that run ("kit2_afreg2/00054_after-wide.DAT", qualified), and a proof found in two folders counts
once (report_proofs). Any other run is reported by itself; --alone reports the main run by itself into
report_alone.json and report_alone.md, leaving report.json, which schema_update reads, as it is. A checklist box
unticked on its own (filter_run.py --untick) is its item's row in the state "box ticked" (row_name).

A list that offered one option only is proved by its display (prove_run's "proof": "display"): the label read off
the screen writes the value its row's records held, a seen value like any other, its name backed by the readers that
read it as any option's is.

A registration mirror line ("kind": "registration mirror": kit/provers/memreg_run.py's, a live setting chosen in its
menu and a memory slot registered to see the slot's copy take it; kit/provers/framepos_run.py --zone-grid's, a frame's
place registered, which no live record holds) is no row's proof: report_proofs leaves it out of the rows, and
registration_mirrors (the live records whose memory copy a registration was seen to take) and mirrored_values (the
values a registration wrote into a memory record no live record holds) read the applied ones for kit/schema_update.py.
A proof line made with the owner's word for a never-open row ("allowance": "the owner allowed <row> remotely, <date>",
runner.allowed_or_exit) gives its words to the records it proved ("allowances"), which the writer carries into each
setting's note evidence.

What does not count: an attempt at a row that did not finish. prove_run tags each list row's attempt and
records it in attempts.jsonl once its last proof (the saved option chosen again) changed nothing; an attempt
with no such line was cut short, or a record stayed changed (a sticky side effect shows up in every later
option's diff), and its proofs are left out. Proofs written before attempts were tagged lose the attempt a
failure that still stands cut short (failures.jsonl, no proof of the row since). Nor does a row made where the camera
stood when lines of the same row that name the state of another row it says nothing of ("Row = option", or in words
"Row option" for a row the proofs walk: state_row) prove all it proves, option by option (stood_rows, stood_out: a
panel's slider proved again with its setup row on --set; AF Area Registration's holds proved again with the run's
setup; a row walked again in pass 3's named states; a row whose records, beside those lines, told a state
the camera was found in). A setting table's cell is named by its row as all the row's cells read it, never with the
values the cells before it held glued on: the walked table's name of the cell at the proof's place (match.cell_options;
one no walked cell matches keeps its own reading with its place, and the report lists it). A label that wrote
two values, or two labels of a one-record list row that wrote one value, is a conflict ("not one to one")
that kit/schema_update.py does not apply (tables and carousels' axes too; a picker's twins, one function listed
twice, are told apart by their place: "AEL hold (2)").

Names (name_of): the map's label stands unless the vision model's reading (a proof's "vlm", or the line
kit/tools/reread_proofs.py wrote for its frame in <run>/readings.jsonl) confirms the bar's OCR instead; the OCR never
wins alone. Each value's source goes into report.json ("names": two readers, one reader (map), vision model (a scale
number the reader alone read), disputed, ocr disagrees...), and the disputed ones and those the OCR disagrees
with into "name_disputes", listed in full in <run>/report.md. A value taken from "nothing changed" (the row's start, and
any option that left the record as it was) keeps its readers' source too: report.json lists such labels apart
("inferred", two or more in a record), for a person to read; the definition never says which they are, for one of them
is the value the record held when the row began (docs/decisions/0016). A table row that proved only a sample stepped from
the option the camera held (prove_run --picker-sample: sampled_from_start) marks its records "sampled_from_start": the
definition counts its proofs and lists none of its values, which would tell that option. A value a record kept from the
option before while
other records moved is carried over: reported ("carried_over", report.md) and not credited to the option's label,
except where a hand rule already names that record. The run's downloads must be that definition's camera and firmware
(camkit.models); --no-schema reports a run with every record "new": another body's, or a camera's with no definition
yet.
"""
import argparse
import collections
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from camkit import ROOT, camset, datafiles, definitions, jsonl, match, models, paths, runs  # noqa: E402
from runner import read_json, write_json  # noqa: E402


LOOKALIKE = str.maketrans("СсАаЕеОоРрТтНМВК–—→", "CcAaEeOoPpTtHMBK-->")


def norm(t) -> str:
    """Compared without case, spaces, dots, arrows, OCR look-alikes or spelled-out signs
    ("-(minus) -> 0 -> +(plus)" is the camera's "-→0→+")."""
    t = re.sub(r"\s*(->|–>|—>|→)\s*", ">", unicodedata.normalize("NFKC", str(t or "")))
    t = re.sub(r"\((minus|plus)\)", "", t.translate(LOOKALIKE).lower())
    t = t.replace("|", "i").replace("l", "i")         # OCR's l for I ("5 lmg." on the camera's "5 Img.")
    return re.sub(r"[\s.:()/>]+|seconds?|sec", "", t)


def close(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()


TICKED, UNTICKED = re.compile(r"allow|tick|\bon\b|target|includ|regist", re.I), re.compile(r"exclud|\boff\b|not", re.I)


def judge_ticks(vals: dict, known: dict) -> tuple:
    """A checklist box: the schema's word for the value written when ticked must mean ticked
    ("Allowed (ticked)"), and the other one unticked ("Excluded")."""
    notes = []
    for lab, v in vals.items():
        s = known.get(v) or ""
        want_on = lab.endswith(": ticked")
        ok = (TICKED.search(s) and not UNTICKED.search(s)) if want_on else bool(UNTICKED.search(s))
        if not ok:
            notes.append({"value": v, "camera": lab, "schema": s or None, "kind": "conflict" if s else "missing"})
    kinds = {n["kind"] for n in notes}
    return ("conflict" if "conflict" in kinds else "missing" if kinds else "agrees"), notes


def strip_icon(t: str) -> str:
    """A picker label without the icon OCR reads in front: one character, or two with a mark
    ("• î Fixed Speed SBY", "R Focus Area", "% Creative Look"); "AF On" keeps its "AF"."""
    return re.sub(r"^(?:(?:\S|[^\sA-Za-z0-9]\S|\S[^\sA-Za-z0-9])\s+)+", "", str(t or "")).strip()


def picker_stars(o: dict) -> int | None:
    """The stars on a picker row ("Add Rating" for each count read alike, 2026-10-29), counted from
    the pixels of the frame the proof chose it on."""
    from camkit import screen
    from camkit.frames import load
    f = paths.run_root() / "kit2_pass2" / "shots" / (o.get("chosen_frame") or "")
    if not o.get("chosen_frame") or not f.exists():
        return None
    img = load(f)
    s = screen.read(img)
    return screen.count_stars(img.image, s.bar) if s.bar else None


SURE: set = set()          # picker labels the OCR and the vision model both gave
# every dash OCR or the reader may write for a minus sign, kept as one: −, –, ‐, ‑, —, ﹣, －
SCALE_DASHES = str.maketrans(dict.fromkeys("\u2212\u2013\u2010\u2011\u2014\ufe63\uff0d", "-"))


def scale_clean(s: str) -> str:
    """A reading of a scale's number (kit/provers/scale_run.py) cut to a number's characters, every dash first made a
    minus sign (SCALE_DASHES), OCR's and the reader's alike: "−1" is "-1" whoever read it, "±0", "‡0" (OCR's ±) and
    "+-0" are "0", "+2" stays."""
    t = re.sub(r"[^0-9A-Za-z+\-.%]", "", str(s or "").translate(SCALE_DASHES))
    return re.sub(r"^(?:\+-|-\+)(?=0+(?:\.0+)?%?$)", "", t)


def scale_key(v: str) -> str:
    """A cleaned scale reading (scale_clean) as two readings of one number are compared: "+2" and "2", "+0", "-0" and
    "0", "80%" and "80" one number, whoever read it (OCR may give the sign the reader leaves out). scale_run walks a
    scale by it, and name_of counts a scale line's two readers by it."""
    v = str(v or "").removesuffix("%").removeprefix("+")
    return "0" if re.fullmatch(r"-?0+", v) else v


def picker_label(o: dict) -> str:
    """A function's name from a picker proof: the OCR without its icon, or the vision model's
    reading when that is close and no shorter (it drops glued icons, "8Var. Shutter" -> "Var.
    Shutter", and reads the arrows, "Move AF Frame ↕ : L"; it also misnames: "Operation Customize"
    for "Not set", "Fixed Speed" for "Fixed Speed STBY")."""
    t = strip_icon(o.get("shown") or o["label"])
    if re.search(r"rating\s*\(", t, re.I) and (n := picker_stars(o)):
        return re.sub(r"\(.*", "(" + "★" * n + ")", t)
    v = str(o.get("vlm") or "")
    if v and close(v, t) >= 0.75 and len(norm(v)) >= len(norm(t)) - 2:
        if close(v, t) >= 0.9:
            SURE.add(v)
        return v
    return t


AGREE = 0.8                # two readings this alike (close) name the same thing


def alike(a: str, b: str) -> bool:
    """Two readings of one name: AGREE alike, or one held whole in the other (the vision model reads "FINE" of the
    camera's "FINE Fine", the OCR doubles "4:3" as "4:3 4:3")."""
    x, y = sorted((norm(a), norm(b)), key=len)
    return close(a, b) >= AGREE or (len(x) >= 2 and x in y)


def glued_icon(label: str, shown: str) -> bool:
    """The map's label is a reading with one icon glyph in front ("LRight 1/2", "DLower Right", "EFocus Frame
    Display", the radio circle in "O JPEG" and "0 1 (Fast)"): the reading without it is the name. Only one glyph is
    dropped, never a word of its own ("RAW Compressed" keeps its RAW)."""
    return bool(shown) and len(label) in (len(shown) + 1, len(shown) + 2) and label[1:].lstrip() == shown and \
        (shown[:1].isupper() and not label[0].isdigit() or label[0] in "0oO" and label[1:2] == " ")


def unglue(L: str, S: str, V: str) -> str:
    """The map's label without what OCR glued on: one glyph in front where the rest is the OCR's or the vision
    model's reading (glued_icon); one stray capital in front of both L and S where they agree on the rest ("EUpper
    Right" / "HUpper Right" are "Upper Right"); and the OCR's fuller name where it is a word and then L ("RAW
    Compressed" for "Compressed"), unless the vision model reads it otherwise."""
    for r in (V, S):
        if r and glued_icon(L, r) and (not V or close(V, r) >= close(V, L)):
            return r
    stray = re.compile(r"[A-Z][A-Z][a-z]")
    if S and len(S) == len(L) and L[0] != S[0] and L[1:] == S[1:] and stray.match(L) and stray.match(S):
        return L[1:]
    m = re.fullmatch(r"([A-Za-z]{2,}) (.+)", S or "")
    if m and m[2] == L and m[1].lower() != L.split()[0].lower() and (not V or alike(V, S)):
        return S
    return L


def part_of(v: str, label: str) -> bool:
    """The vision model read one part of a two-part name: each of its words (two or more) is a word of the label, or
    the label's abbreviation of it ("5 Images" of "2.0 EV 5 Img.", "2 Images (+)" of "0.3 EV 2 Img. +": the bracket's
    images axis without its step)."""
    words = lambda t: re.findall(r"[a-z]+|\d+|[+-]", str(t).lower())
    wv, wl = words(v), words(label)

    def sub(a: str, b: str) -> bool:          # a's letters in order in b, from b's first letter
        it = iter(b)
        return a[:1] == b[:1] and all(c in it for c in a)
    return len(wv) >= 2 and all(any(w == u or (w.isalpha() and u.isalpha() and (sub(u, w) or sub(w, u))) for u in wl)
                                for w in wv)


ROW_NAMES: set = set()     # the run's menu rows (norm), main fills it: a vision reading that names one read a row
MENU_NAMES: set = set()    # every row and group of the camera's menu tree (norm), main fills it (menu_names): for an
#                            Add Item proof, whose option is a row, a reading that is another's is a neighbour or the header


def reads_a_row(v: str) -> bool:
    """The vision model read a menu row, the screen's title or a button (BUTTONS), not the option ("ISO AUTO Minimum" on that row's
    list, "Focus Area" on a Recall Custom hold's page): the reading says nothing about the option's name."""
    n = norm(v)
    return bool(n) and (n in BUTTONS or any(n == r or (len(n) >= 4 and r.startswith(n)) for r in ROW_NAMES))


BUTTONS = {"register", "ok", "cancei", "enter", "back", "menu"}     # norm of the screens' button words ("Register")


def menu_names(tree) -> set:
    """norm() of every row label and group name in the camera's menu tree (private/evidence/<model>_fw<fw>/menu_tree_...,
    `tree`, a path or None; none when it is not there: camkit.datafiles), every mode's. An Add Item proof's option is a menu row itself, so a vision reading that is another
    row's name or a page's group ("AF/MF" over Preset Focus/Zoom, 2026-11-07) is a neighbour or the header read, never
    the item (name_of leaves it out, as reads_a_row does a row's name over an option)."""
    names = set()
    if tree and not Path(tree).exists():
        datafiles.say_no_menu_tree(tree, "a vision reading that names another menu row or a page's group is checked "
                                         "against the proofs' own rows only, so a few more may be taken for the item")
    elif tree:
        doc = datafiles.load_menu_tree(tree)
        for tabs in [doc.get("tabs") or []] + [m.get("tabs") or [] for m in doc.get("modes") or []]:
            for tb in tabs:
                for pg in tb.get("pages") or []:
                    names.add(norm(pg.get("group")))
                    names.update(norm(r.get("label")) for r in pg.get("rows") or [])
    names.discard("")
    return names


def name_of(o: dict) -> tuple:
    """(name, source, dispute) for one proof: the name its value is credited to, which readers back it, and, for a
    name the readers do not agree on, {label, shown, vlm} to look at (else None). Readers: the pass-1 map's label L
    (mostly two readers agreed), the bar's OCR at OK time S (the weakest) and the vision model's reading at OK time V
    (a proof's "vlm", or kit/tools/reread_proofs.py's). The vision model breaks ties, never overrides alone: it can
    read another row ("Focus Mode" for a hold's "F11").
      sidelist          L (OCR of the bar drops signs)
      dialog, axis, lookbase   today's carousel rule: S when it reads like L, for S carries the axis value shown now
      V ~ L             L, "two readers" (~: alike, AGREE alike or one held whole in the other)
      V ~ S, S != L     S, "two readers" (the vision model confirms the OCR's reading; AGREE alike only)
      V a part of L     L, "one reader (map)" (part_of: one axis of a two-part name)
      V far, S == L     L, "two readers" (the map and the bar's OCR read it alike; the vision model read something
                        else on the screen; a scale line is counted apart, below)
      V far from both   L, "disputed"
      no V, S ~ L or no S   L, "one reader (map)"
      no V, S far from L    L, "ocr disagrees" (never S: OCR of two slot icons read "1/7 This Image")
    A vision reading far from L that names a menu row (reads_a_row), or, on an Add Item proof, any row or group of the
    menu tree (MENU_NAMES), is not counted. Stars are counted from pixels
    ("pixels"), a look's or fields' number is the value set ("number"), and a picker's
    function is picker_label's ("two readers" when V backs it, else "one reader (ocr)"). A scale prover's line whose
    number the reader alone read on the frame chosen (read_by "reader": OCR read none there, and V is the same answer
    that read it) is one reader, never two: L, "vision model" (2026-11-09). Any other scale line ("scale": true) has
    L and S from one OCR reading of the number, so its readers are OCR and the vision model: "two readers" only when V
    is the same number (scale_key), else L, "one reader (ocr)" (a scale's end word "Fast", or the next number)."""
    kind, L, S, V = o["kind"], str(o["label"]), o.get("shown") or "", str(o.get("vlm") or "")
    if kind == "look":
        return (f"{o['value']:+d}" if o["value"] else "0"), "number", None
    if kind == "fields":
        return (o["kept"] if o.get("applied") is False else o["value"]), "number", None
    if kind == "table" and o.get("opens") == "picker":
        lab = picker_label(o)
        return lab, ("two readers" if V and close(V, lab) >= AGREE else "one reader (ocr)"), None
    if o.get("read_by") == "reader":
        return L, "vision model", None     # kit/provers/scale_run.py: V is the one answer that read the number
    if o.get("scale"):
        same = V and scale_key(scale_clean(V)) == scale_key(scale_clean(L))
        return L, ("two readers" if same else "one reader (ocr)"), None
    if re.search(r"[★→]", L):
        return L, "pixels", None           # stars are counted from pixels and checked live; OCR reads "*", "+"
    if kind == "sidelist":
        return L, ("two readers" if V and close(V, L) >= AGREE else "one reader (map)"), None
    if kind in ("dialog", "axis", "lookbase"):
        # the title the camera showed is the fuller name only when it reads like the label: a slot's title is its
        # contents (Custom Look 5 shows the look it was made from, the user's own: 2026-10-29)
        lab = L if not S or close(S, L) < 0.5 else S
        return lab, ("two readers" if V and close(V, lab) >= AGREE else "carousel"), None
    L = unglue(L, S, V)
    seen = {"label": str(o["label"]), "shown": S or None, "vlm": V or None}
    if V and not alike(V, L) and (reads_a_row(V) or (o.get("my_menu") and norm(V) in MENU_NAMES)):
        V = ""                 # another row, a header or a button read: nothing about this option's name
    if V:
        if alike(V, L):
            return L, "two readers", None
        if S and norm(S) != norm(L) and close(V, S) >= AGREE:
            return S, "two readers", None
        if part_of(V, L):
            return L, "one reader (map)", None
        if S and norm(S) == norm(L):
            return L, "two readers", None
        return L, "disputed", seen
    if not S or alike(S, L):
        return L, "one reader (map)", None
    return L, "ocr disagrees", seen


def judge_functions(vals: dict, known: dict) -> tuple:
    """A function picker's record: the code is what was proved; the schema's label stands when the
    camera's reading is loosely like it (OCR of icons and arrows), and only labels nothing like it
    are conflicts, for a person to look at."""
    notes, worst = [], "agrees"
    for lab, v in vals.items():
        s = known.get(v)
        if s and close(s, lab) >= 0.6:
            continue
        kind = "missing" if not s else "conflict"
        notes.append({"value": v, "camera": lab, "schema": s, "kind": kind, "sure": lab in SURE})
        worst = "conflict" if kind == "conflict" or worst == "conflict" else "missing"
    return worst, notes


def contained(s: str, lab: str, vals: dict) -> bool:
    """The schema's label s read inside the camera's lab counts as agreement only when no other proved label of the
    record holds it as well: the schema's "Hi" under the camera's "Cont. Shooting: Hi" is not agreement while
    "Cont. Shooting: Hi+" is proved too. A label of three characters or more may sit anywhere in lab; a shorter one
    only as a whole word ("5" in "5(Wide)", "S" in "Spot: S"; never "M" in "Medium" or "P" in "Program Auto")."""
    def fit(t: str) -> int:              # 2: a whole word, 1: anywhere (three characters or more), 0: not held
        n = norm(s)
        if not n or n not in norm(t):
            return 0
        if re.search(r"(?<![A-Za-z0-9])" + re.escape(str(s).strip()) + r"(?![A-Za-z0-9])", str(t), re.I):
            return 2
        return 1 if len(n) >= 3 else 0
    q = fit(lab)
    return q > 0 and not any(o != lab and fit(o) >= q for o in vals)


def abbreviates(s: str, lab: str, vals: dict) -> bool:
    """The schema's label is an initial or the start of a word of the camera's label, as a whole word ("M" for
    "Manual Exposure", "Med" for "Medium", "Hi" for "Cont. Shooting: Hi"), and no other proved label of the record
    fits it as well (the other way round too: the camera's "P" for the schema's "Program Auto", among the schema's
    other labels). Words every proved label shares ("Movie:") do not count, a word itself fits best, then the start
    of the first word left, then the start of a later one: "P" is "Program Auto", not "Aperture Priority"."""
    t = str(s or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9+]+", t):
        return False
    words = {o: re.findall(r"[a-z0-9+]+", str(o).lower()) for o in vals}
    common = set.intersection(*(set(w) for w in words.values())) if len(words) > 1 else set()

    def fit(o: str) -> int:
        left = [w for w in words[o] if w not in common]
        if t in left:
            return 3
        return 2 if left and left[0].startswith(t) else 1 if any(w.startswith(t) for w in left[1:]) else 0
    q = fit(lab)
    return q > 0 and all(fit(o) < q for o in vals if o != lab)


def judge(vals: dict, known: dict) -> tuple:
    """(verdict, per-value notes) for one record: vals = proved {label: value}, known = schema {value: label}."""
    notes, worst = [], "agrees"
    rank = ["agrees", "wording", "missing", "conflict"]
    for lab, v in vals.items():
        s = known.get(v)
        if s and (norm(s) == norm(lab) or contained(s, lab, vals)):
            continue
        if s and any(o != lab and vals[o] == v and norm(o) == norm(s) for o in vals):
            continue                          # a value two options share, and the schema names it after the other
        if not s:
            kind = "missing"
        else:
            other = max((o for o in vals if o != lab), key=lambda o: close(s, o), default=None)
            swapped = other is not None and close(s, other) > max(close(s, lab), 0.8)
            kind = "conflict" if swapped or close(s, lab) < 0.4 else "wording"
            if kind == "conflict" and (abbreviates(s, lab, vals) or abbreviates(lab, s, dict.fromkeys(known.values()))):
                kind = "wording"              # the schema abbreviated the camera's words: they replace it
        notes.append({"value": v, "camera": lab, "schema": s, "kind": kind})
        worst = max(worst, kind, key=rank.index)
    return worst, notes


def base_row(name: str) -> str:
    """A row's name without its option or context ("Shoot Mode / Movie [ctx]" -> "Shoot Mode")."""
    return re.split(r" / | \[", name, maxsplit=1)[0]


UNTICK_STATE = "box ticked"      # the state a checklist box's own proof starts from (row_name)


def row_name(r: dict) -> str:
    """The report's row for a proof. Each number field is its own row ("... [field 1]"). A checklist box unticked on
    its own (kit/provers/filter_run.py --untick: "untick", label "Not ticked") is its item's row in the state it needs,
    the box ticked ("Playback Filter Condition > Protect [box ticked]"): in the chooser's row it would take the place of
    the chooser's first option (both index 0) and be credited with what the item's other records held."""
    name = " > ".join(r["path"])
    if r["kind"] == "fields":
        name += f" [field {r['index'][0]}]"
    if r["kind"] in ("axis", "wbgrid", "look", "lookbase", "table"):
        name += f" / {r['option']}"
    if r["kind"] == "look":
        name += f" / {r['param']}"            # each parameter is its own number, written alone
    context = ", ".join(x for x in (r.get("context"), UNTICK_STATE if r.get("untick") else None) if x)
    if context:
        name += f" [{context}]"
    return name


def fail_key(r: dict) -> str:
    """The row a failures.jsonl line names, as still_failing keys it (a proof gives the same key)."""
    k = " > ".join(r["path"])
    return k + f" / {r['option']}" if r.get("kind") in ("axis", "look", "lookbase", "wbgrid", "table") and r.get("option") else k


def proofs_of(run: Path) -> list:
    return jsonl.read(run / "proofs.jsonl")


MAIN_RUN = runs.MAIN_RUN       # the run the definition is written from (kit/schema_update.py's RUN)
# the proof runs read beside it (proof_runs) are the run folders marked as one (runs.PROOF_RUN): kit/provers/afreg_run.py
# keeps its proofs in a run of its own and marks it, filter_run.py marks the run --run names, and proof lines recorded
# by hand into a run's own folder need the mark written with them (the a1 II's AF Area Registration holds of 2026-11-02).
# A run made to check the kit is never marked: kit2_review_list (the review of 2026-11-07/08) proved rows again to test
# the provers, in whatever state the camera was in then, which its proofs do not name; taken in beside the mapping's,
# they would tell that state (docs/decisions/0016)
FILE_FIELDS = ("dat", "base", "chosen_frame", "row_frame", "diffed_with")     # a proof's files, by name in its run
QUALIFIED = re.compile(r"(\w[\w.-]*)/([^/]+)")     # "<run>/<file>": a file as qualified names it


def proof_runs(run: Path, alone: bool = False) -> list:
    """The run folders one report reads, in order: the run, then, for the camera's main run (MAIN_RUN, which
    kit/schema_update.py writes the definition from), the camera's other proof runs (the folders marked runs.PROOF_RUN)
    that hold proofs, by name. Another run, or alone, is read by itself."""
    if alone or run.name != MAIN_RUN:
        return [run]
    side = {p.parent for p in run.parent.glob(f"*/{runs.PROOF_RUN}")}
    return [run] + sorted(p for p in side if p != run and (p / "proofs.jsonl").exists()
                          and (p / "proofs.jsonl").stat().st_size)


_DOWNLOAD_DAYS: dict = {}      # run folder -> {download file name: the day it was made} (download_days)


def download_days(run_dir: Path) -> dict:
    """{download file name: the local date it was made} of a run, from its events.jsonl (the link's log: each download's
    reply names its file). Read once per run."""
    import datetime
    key = str(run_dir)
    if key not in _DOWNLOAD_DAYS:
        days = {}
        for r in jsonl.read(Path(run_dir) / "events.jsonl", bad="skip"):
            path = (r.get("reply") or {}).get("path") if isinstance(r.get("reply"), dict) else None
            if isinstance(path, str) and path.endswith(".DAT") and isinstance(r.get("t"), (int, float)):
                days[re.split(r"[\\/]", path)[-1]] = datetime.date.fromtimestamp(r["t"]).isoformat()
        _DOWNLOAD_DAYS[key] = days
    return _DOWNLOAD_DAYS[key]


def run_date(run_dir: Path) -> str | None:
    """The day a run began: the local date of the first event in its events.jsonl, else the day its proof-run mark was
    written (runs.PROOF_RUN's "since"); None when neither says. A proof's own download's day comes first (proof_day)."""
    import datetime
    try:
        with open(Path(run_dir) / "events.jsonl", encoding="utf-8", errors="replace") as f:
            for line in f:                       # the first line that says when: a long log is not read whole
                try:
                    t = json.loads(line).get("t")
                except (ValueError, AttributeError):
                    continue
                if isinstance(t, (int, float)):
                    return datetime.date.fromtimestamp(t).isoformat()
    except OSError:
        pass
    try:
        since = json.loads((Path(run_dir) / runs.PROOF_RUN).read_text(encoding="utf-8")).get("since")
    except (OSError, ValueError, AttributeError):
        return None
    return since if isinstance(since, str) and re.fullmatch(r"\d{4}-\d\d-\d\d", since) else None


def proof_day(r: dict, root: Path) -> str | None:
    """The day a proof of another run than the main one was made: its download's (download_days), else the day its run
    began (run_date); None for a proof of the main run (the writer dates those as it always has)."""
    if not r.get("run"):
        return None
    q = QUALIFIED.fullmatch(str(r.get("dat") or ""))
    name = q[2] if q else str(r.get("dat") or "")
    return download_days(root / r["run"]).get(name) or run_date(root / r["run"])


def latest_run(came, main: str, main_date: str) -> tuple:
    """(run, date) a record's proof names: of the runs whose proofs proved it (`came`, {run: the day of its latest proof
    of the record, None for the main run}, the report's "runs"), the latest; the main run (`main`) is dated `main_date`,
    as the definition has always dated it, and so is a run whose day is not known."""
    dated = [(day or main_date, name) for name, day in (came or {}).items()]
    if not dated:
        return main, main_date
    day, name = max(dated)
    return name, day


def record_runs(opts: dict, vals: dict, label_of: dict, main: str, root: Path) -> dict:
    """{run: the day of its latest proof} of the proofs a record's values come from (each proof's "run", qualified, with
    proof_day; the main run's proofs as {main: None}): the options credited with a label of `vals`, else every option of
    the row that applied."""
    labels = {str(lab) for lab in vals}
    hit = [o for i, o in opts.items() if str(label_of.get(i, name_of(o)[0])) in labels]
    out = {}
    for o in hit or [o for o in opts.values() if o.get("applied") is not False]:
        run, day = o.get("run") or main, proof_day(o, root) if o.get("run") else None
        out[run] = max(filter(None, (out.get(run), day)), default=None)
    return dict(sorted(out.items()))


def qualified(r: dict, home: str, main: str) -> dict:
    """A proof as the report reads it: one made in a run of its own (its "run": a proof recorded into the main run by
    hand or through the SDK; else the run folder it was read from, home) names its files with that run in front
    ("kit2_afreg2/00054_after-wide.DAT"), and says the run, so the files of two runs that share a name
    ("00001_before.DAT") are never one (base_value, carried_over, unfinished, a reading of a frame)."""
    own = r.get("run") or home
    if own == main:
        return r
    return {**r, "run": own, **{f: f"{own}/{r[f]}" for f in FILE_FIELDS if isinstance(r.get(f), str) and r[f]
                                and "/" not in r[f]}}         # a path ("../../kit2_dial/dat/...") stays as written


MIRROR_KIND = "registration mirror"      # memreg_run.py's and framepos_run.py --zone-grid's lines (mirror_lines)


def mirror_lines(run: Path, alone: bool = False) -> list:
    """The applied registration mirror lines (MIRROR_KIND) of the runs the report reads (proof_runs), qualified with
    their run (a line of the main run as it is), in order: a memory slot registered after a live setting was chosen
    (memreg_run.py: "live" names the live record, "record" its copy), or after a frame was moved (framepos_run.py
    --zone-grid: "record" alone, the place no live record holds)."""
    out = []
    for part in proof_runs(run, alone):
        out += [qualified(r, part.name, run.name) for r in jsonl.read(part / "proofs.jsonl")
                if r.get("kind") == MIRROR_KIND and r.get("applied") is True]
    return out


def mirror_day(r: dict, run: Path) -> str | None:
    """The day a registration mirror line was made: its download's (proof_day), else its run's first day."""
    return proof_day(r, run.parent) or run_date(run.parent / (r.get("run") or run.name))


def registration_mirrors(run: Path, alone: bool = False) -> dict:
    """{live key: {"run", "date", "slot", "allowance"?}}: each live record whose memory copy a registration was seen
    to take (mirror_lines with "live"), its latest line's run, day and memory slot, and the owner's allowance the line
    carries. Keys and those only: never a value (docs/decisions/0016)."""
    out = {}
    for r in mirror_lines(run, alone):
        if not r.get("live") or not str(r.get("slot") or "").isdigit():
            continue
        got = {"run": r.get("run") or run.name, "date": mirror_day(r, run), "slot": int(r["slot"]),
               **({"allowance": r["allowance"]} if r.get("allowance") else {})}
        was = out.get(r["live"])
        if was is None or (got["date"] or "", got["run"]) >= (was["date"] or "", was["run"]):
            out[r["live"]] = got
    return out


def mirrored_values(run: Path, alone: bool = False) -> dict:
    """{record key ("set:0x0f32"): {"values": {code: label}, "run", "date", "menu", "allowance"?}}: the values a
    registration wrote into a memory record no live record holds (mirror_lines without "live": framepos_run.py
    --zone-grid's zone places), each code with the line's label, the latest line's run and day."""
    out = {}
    for r in mirror_lines(run, alone):
        if r.get("live") or not r.get("record") or not isinstance(r.get("index"), int):
            continue
        got = out.setdefault(r["record"], {"values": {}, "run": None, "date": None, "menu": r.get("menu") or ""})
        got["values"][r["index"]] = r.get("label")
        day, by = mirror_day(r, run), r.get("run") or run.name
        if (day or "", by) >= (got["date"] or "", got["run"] or ""):
            got.update(run=by, date=day)
        if r.get("allowance"):
            got["allowance"] = r["allowance"]
    return out


def record_allowances(opts: dict, vals: dict, label_of: dict) -> list:
    """The owner's allowances (a proof line's "allowance") of the proofs a record's values come from: the options
    credited with a label of `vals`, else every option of the row that applied (as record_runs picks them)."""
    labels = {str(lab) for lab in vals}
    hit = [o for i, o in opts.items() if str(label_of.get(i, name_of(o)[0])) in labels]
    return sorted({o["allowance"] for o in hit or [o for o in opts.values() if o.get("applied") is not False]
                   if o.get("allowance")})


def same_proof(r: dict) -> tuple | None:
    """What one proof is, whichever run folder it was read from: its run's files, row, option and label. A proof copied
    into a second folder is counted once (report_proofs). None for a proof that names no download."""
    if not r.get("dat"):
        return None
    return (r.get("run"), r["dat"], r.get("base"), row_name(r), json.dumps(r.get("index")), str(r.get("label")))


def report_proofs(run: Path, alone: bool = False) -> tuple:
    """(proofs, skip, blocked, failed, reread) over the runs the report reads (proof_runs): each run's proofs in order,
    qualified, a proof read before in another folder left out (same_proof), a registration mirror line left out
    (MIRROR_KIND: mirror_lines reads those); skip, the indices of those that do not count,
    as unfinished says for each run by its own attempts and failures; blocked and failed, still_failing over all of
    them; reread, how many proofs took a reading of their frame (attach_readings). The put-back notes of every run's
    finished attempts go into PUT_BACK. A setting table's cell is named as the camera's walked table names it, the
    cell at the proof's place (match.cell_options over the runs' kit2_tables/tables.json: a cell's own reading of its
    row label carries the values of the cells before it, the camera's own settings); a cell no walked cell matches
    keeps its own reading with its place, and UNWALKED_CELLS says which and why. The proofs' downloads are read from
    the run's folders (base_value)."""
    _BASE_DIRS[:] = [run / "dat", run]
    _RUNS_ROOT[:] = [run.parent]
    proofs, skip, blocked, failed, reread, seen = [], set(), {}, {}, 0, set()
    for part in proof_runs(run, alone):
        own = []
        for r in jsonl.read(part / "proofs.jsonl"):
            if r.get("kind") == MIRROR_KIND:
                continue                       # a registration's copy, no row's proof (mirror_lines reads it)
            r = qualified(r, part.name, run.name)
            key = same_proof(r)
            if key is not None and key in seen:
                continue                       # the same proof read in another folder
            seen.add(key)
            own.append(r)
        reread += attach_readings(part, own, "" if part == run else part.name + "/")
        PUT_BACK.update(put_back_notes(part))
        skip |= {len(proofs) + i for i in unfinished(own, attempts_done(part), failing_frames(part))}
        b, f = still_failing(part)
        blocked.update(b)
        failed.update(f)
        proofs += own
    tables = run.parent / "kit2_tables" / "tables.json"
    proofs, unwalked = match.cell_options(proofs, read_json(tables) if tables.exists() else None)
    UNWALKED_CELLS.clear()
    UNWALKED_CELLS.update({row_name(r): unwalked[r["option"]] for r in proofs
                           if r.get("kind") == "table" and r.get("option") in unwalked})
    return proofs, skip, blocked, failed, reread


# a setting table's row whose cell no walked cell matched (match.cell_options): named by its own proofs' reading of
# it, with its place, which may carry a value the camera held; row -> why. report.json's entry says so ("cell_name")
UNWALKED_CELLS: dict = {}


STATE_ITEM = re.compile(r"(.+?) = .+")    # "Row = option": a context's or a setup's item naming a row's state


def state_items(r: dict) -> list:
    """A proof's context items (split at "," and ";") and setup rows (kit/provers/afreg_run.py's "setup": the rows the
    run set before it)."""
    return [w.strip() for w in re.split(r"[,;] ", r.get("context") or "") + list(r.get("setup") or []) if w.strip()]


def walked_rows(proofs: list) -> dict:
    """{norm(name): name} of every menu row the proofs walk (each part of their paths, a context aside): the rows a
    context item can name the state of in words (state_row)."""
    return {norm(n): n for r in proofs for p in r.get("path") or [] if (n := re.split(r" \[", p)[0].strip())}


def state_row(item: str, rows: dict) -> str | None:
    """The row whose state a context item names: "Row = option" ("Monitor Brightness > Brightness Setup = Manual",
    "Switch V/H AF Area = Off"), or in words, "Row option" or "Row: option", where Row is a row the proofs walk (rows:
    walked_rows), the longest that fits, and the words after it hold no ":" of their own ("Recording Media Sort
    Recording", "Shoot Mode A (dial set with the menu)", "Exposure step 0.5EV", "File Format: SLOT 1 JPEG", "Switch V/H
    AF Area Off"). None for an item that names no row so ("Movie mode", "camera level", "PAL", "Spot size last left:
    XL"): such an item names no state the rule can see, and a row it stands beside is kept."""
    if m := STATE_ITEM.fullmatch(item):
        return m[1]
    words = item.split(" ")
    for n in range(len(words) - 1, 0, -1):
        head, rest = " ".join(words[:n]), " ".join(words[n:])
        if norm(head) in rows and (head.endswith(":") or ":" not in rest):
            return rows[norm(head)]
    return None


def named_states(r: dict, rows: dict | None = None) -> frozenset:
    """The rows whose state a proof names (state_row, of each item of its context and setup): a Monitor Brightness line
    of kit/provers/scale_run.py --panel-row with its --set names {"Monitor Brightness > Brightness Setup"}, a pass-3
    line in "Shoot Mode A (dial set with the menu), Recording Media Sort Recording, Exposure step 0.5EV" names
    {"Shoot Mode", "Recording Media", "Exposure step"}. rows: walked_rows of the proofs; without it, only items
    of the form "Row = option" name one."""
    return frozenset(s for w in state_items(r) if (s := state_row(w, rows or {})))


def says_of(r: dict, row: str, rows: dict | None = None) -> bool:
    """Whether a proof's context or setup speaks of a row at all: an item naming its state or a part of it ("Mode Dial
    Control Set / Drive Mode Dial = ..." speaks of Mode Dial Control Set; "Switch V/H AF Area Off" of Switch V/H AF
    Area), or an item naming no row's state (state_row) that holds the row's name as whole words, not as the start of
    a longer row's ("Focus Area Limit = ..." names Focus Area Limit, and says nothing of Focus Area; "the hold's Shoot
    Mode Manual Exposure" speaks of Shoot Mode). A row a line speaks of is never the state it is left out for
    (stood_rows); when unsure, it speaks."""
    rows = rows or {}
    longer = [n for k, n in rows.items() if k != norm(row) and k.startswith(norm(row))]
    for w in state_items(r):
        s = state_row(w, rows)
        if s is not None:
            if norm(s) == norm(row) or s.startswith((row + " / ", row + " > ")):
                return True
            continue
        for m in re.finditer(r"(?<!\w)" + re.escape(row) + r"(?!\w)", w, re.I):
            if not any(w[m.start():].lower().startswith(n.lower()) for n in longer):
                return True
    return False


def stood_rows(proofs: list, skip: set = frozenset()) -> dict:
    """{report row: (its lines' indices into proofs, the rows that stand for it)}: each report row (row_name: a row in
    one context) that says nothing of a row X (says_of), beside lines of the same row that name X's state and every
    state the row names (named_states), the lines that stand for it, such that each of its lines chooses an option
    (index and label; a setting table's cell by its label alone, its list numbered from the option it opened on) some
    line that stands for it chooses too, and for each record its line changed, to value v, a line that stands for it
    and chooses the same option either changes that record to v as well or leaves it alone while its own base download
    already holds v (base_value: a record that held an option's value before does not change when the option is chosen
    again); and no line that stands for it changes that record to another value under that option. Whether a row
    depends on X shows in the records it changed (the orientations an AF area wrote, a panel's slider being there at
    all), so a row made where the camera stood can tell X's state as the camera was found in (docs/decisions/0016). A row with a line not applied or a box unticked on its own is no such
    row, and neither is any row beside no line that names a state. The lines that stand for a row name more states
    than it, so two rows never stand for each other. skip: indices that already do not count, never taken as either.
    The report leaves out those of them whose every value its records credit the rows that stand for them credit as
    well, backed by readers as well (stood_out); the writer reads the lines the report left out (stood_on)."""
    rows_walked = walked_rows(proofs)

    def option(r):
        if r.get("kind") == "table":
            return None, norm(r.get("label"))
        return json.dumps(r.get("index")), norm(r.get("label"))

    def counted(r):
        return r.get("applied") is not False and r.get("planned") is not False

    def stands_for(change, chosen):
        """Whether a line of the same option backs one change of the row's line (stood_rows)."""
        k, v = change.get("key"), json.dumps(change.get("after"))
        wrote = [json.dumps(c.get("after")) for c in chosen.get("changes") or [] if c.get("key") == k]
        if wrote:
            return v in wrote
        return json.dumps(base_value(chosen.get("base"), k)) == v

    by_row = collections.defaultdict(list)          # a row in every context (row_name without one) -> its lines
    for i, r in enumerate(proofs):
        if i not in skip and r.get("path"):
            by_row[row_name(dict(r, context=None, untick=None))].append(i)
    out = {}
    for lines in by_row.values():
        named = {i: named_states(proofs[i], rows_walked) for i in lines}
        rows = collections.defaultdict(list)
        for i in lines:
            rows[row_name(proofs[i])].append(i)
        every = set().union(*named.values())
        for row, own in rows.items():
            if not all(counted(proofs[i]) and not proofs[i].get("untick") for i in own):
                continue
            states = set().union(*(named[i] for i in own))
            for x in sorted(every - states):
                if any(says_of(proofs[i], x, rows_walked) for i in own):
                    continue
                cover = [proofs[j] for j in lines if x in named[j] and states <= named[j] and counted(proofs[j])]
                by_option = collections.defaultdict(list)
                for o in cover:
                    by_option[option(o)].append(o)
                if cover and all(option(proofs[i]) in by_option and all(
                        any(stands_for(c, o) for o in by_option[option(proofs[i])])
                        and not any(c2.get("key") == c.get("key") and json.dumps(c2.get("after")) != json.dumps(c.get("after"))
                                    for o in by_option[option(proofs[i])] for c2 in o.get("changes") or [])
                        for c in proofs[i].get("changes") or []) for i in own):
                    out[row] = (frozenset(own), frozenset(row_name(o) for o in cover))
                    break
    return out


def stood_on(proofs: list, skip: set = frozenset(), reported=None) -> set:
    """Indices into proofs that do not count: the lines of the rows stood_rows finds, a row the report kept (its name
    among `reported`, report.json's rows: stood_out found a value or a reader there the rows that stand for it lack)
    aside. kit/schema_update.py reads them so: a value only they wrote is not kept from an older definition
    (writer.proofs.written_values)."""
    return {i for row, (own, _) in stood_rows(proofs, skip).items() if reported is None or row not in reported
            for i in own}


def credit_inputs(proofs: list, skip: set, rows: dict, hand: set) -> tuple:
    """(carried, not_credited, kept_over, owners): what values_of needs of every row beside one's own. carried: the
    values carried over (carried_over), each marked whether a hand rule names its record; not_credited: those no hand
    rule names, by download and record; kept_over: all of them so (a value a hand rule names is still the option
    before's when the records a function's own screen writes are told apart: Rating's copies (0x16bd-0x16c1), which
    the next key option kept, are Rating Set's, not that option's, though KEEP_LABELS names them; 2026-11-08: crediting
    them to the AEL key put "Ticked" on every playback key); owners: each row's records its (not checklist) proofs
    change."""
    carried = carried_over(proofs, skip)
    for c in carried:
        c["hand_rule"] = c["key"].split("[")[0] in hand
    not_credited = frozenset((c["dat"], c["key"]) for c in carried if not c["hand_rule"])
    kept_over = frozenset((c["dat"], c["key"]) for c in carried)
    owners = {row: {c["key"] for o in opts.values() if o["kind"] != "checklist" and o.get("applied") is not False
                    for c in o.get("changes") or []} for row, opts in rows.items()}
    return carried, not_credited, kept_over, owners


def row_values(rows: dict, name: str, opts: dict, schema: dict, owners: dict, not_credited: frozenset,
               kept_over: frozenset, readouts: frozenset) -> tuple:
    """(records, inferred, sources, disputes, held back) of one report row, as values_of credits them. A record another
    (not checklist) row's proofs change is that row's: in a checklist it moved with the setting in use (Focus Area Limit
    unticking the area in use, 2026-10-30)."""
    elsewhere = frozenset(k for row, keys in owners.items() if base_row(row) != base_row(name) for k in keys)
    inferred, sources, disputes, held_back = {}, {}, {}, {}
    recs = values_of(opts, elsewhere, {k: x["name"] for k, x in schema.items()}, own_records(rows, name, opts),
                     inferred, not_credited, sources, disputes, kept_over, no_credit(rows, name, opts, readouts),
                     held_back)
    return recs, inferred, sources, disputes, held_back


def reader_rank(said) -> int:
    """How well a report's name source backs a name, as the writer ranks it (writer.proofs.READER_RANK): two readers 0,
    any single reading 1, the vision model alone 2."""
    return {"two readers": 0, "vision model": 2}.get(said, 1)


def stood_out(run: Path, proofs: list, skip: set, schema: dict, hand: set, readouts: frozenset) -> set:
    """The indices of the rows stood_rows finds whose every value the report credits on a record (values_of, which
    also credits a value no line changed: a final line's, a start's) the rows that stand for them credit on that
    record too, its name backed by readers at least as well (reader_rank), in a row not sampled from the option the
    camera held: leaving such a row out loses no value and no name of the definition, only its menu row. Each row is
    credited as the report credits it with every row of stood_rows still there."""
    found = stood_rows(proofs, skip)
    if not found:
        return set()
    rows = rows_of(run, proofs, skip)
    _, not_credited, kept_over, owners = credit_inputs(proofs, skip, rows, hand)
    memo = {}

    def credited(name):          # {record: {value: best rank}}
        if name not in memo:
            recs, _, sources, _, _ = row_values(rows, name, rows[name], schema, owners, not_credited, kept_over,
                                                readouts)
            out = collections.defaultdict(dict)
            for key, vals in recs.items():
                for lab, v in vals.items():
                    v, rank = json.dumps(v), reader_rank((sources.get(key) or {}).get(lab))
                    out[key][v] = min(rank, out[key].get(v, rank))
            memo[name] = out
        return memo[name]

    out = set()
    for row, (own, cover) in found.items():
        if row not in rows or sampled_from_start(rows[row]):
            continue
        best = collections.defaultdict(dict)
        for c in cover:
            for key, vals in credited(c).items():
                for v, rank in vals.items():
                    best[key][v] = min(rank, best[key].get(v, rank))
        if all(v in best[key] and best[key][v] <= rank for key, vals in credited(row).items()
               for v, rank in vals.items()):
            out |= own
    return out


def frame_no(name) -> int:
    """A frame's or download's number, also of one named with its run in front (qualified, QUALIFIED)."""
    q = QUALIFIED.fullmatch(name or "")
    m = re.match(r"(\d+)_", q[2] if q else name or "")
    return int(m.group(1)) if m else 0


def proof_frame(r: dict) -> int:
    return max(frame_no(r.get("chosen_frame")), frame_no(r.get("dat")))


def attempts_done(run: Path) -> set:
    """The attempts prove_run finished (attempts.jsonl: {"attempt", "row", "complete": true})."""
    return {a["attempt"] for a in jsonl.read(run / "attempts.jsonl") if a.get("complete")}


PUT_BACK: dict = {}            # attempt -> what its put-back left differing and why (prove_run.put_back_leftovers)


def put_back_notes(run: Path) -> dict:
    """{attempt: {"kept": [keys], "not_offered": [keys], "mirrors": {key: {"box", "ticked"}}}} from attempts.jsonl:
    the records a finished attempt's put-back left differing and the prover's reason (2026-11-07). A kept record
    was set by one option as a side effect and held since (the keys Flexible Exp. Mode reassigns): it is no value
    of this row's, so it is credited to no option. A mirrored record is a copy of a box's tick: credited to that
    box, ticked and unticked, whatever visit moved it."""
    return {a["attempt"]: a["put_back"] for a in jsonl.read(run / "attempts.jsonl")
            if a.get("complete") and a.get("put_back")}


def side_kept(o: dict) -> set:
    """The record keys the prover found kept as a side effect in the option's attempt (none without a note)."""
    return set((PUT_BACK.get(o.get("attempt")) or {}).get("kept") or ())


def side_named(o: dict) -> set:
    """The record keys a proof names in its "side_effects" (by key, as kit/provers/afreg_run.py writes them, or as dicts
    with their values, as a by-hand proof records them): records its visit wrote, or may have written, that are no value
    of its option, so it is never credited with what they held."""
    return {x.get("key") if isinstance(x, dict) else x for x in o.get("side_effects") or ()} - {None}


def unfinished(proofs: list, done: set, failing: dict) -> set:
    """Indices into proofs that do not count: a tagged attempt with no completion line; and, for proofs written
    before attempts were tagged (a carousel's axis proofs still are not), each attempt a failure cut short (failing:
    {fail_key: the frames of its failures}, failing_frames: a row that still fails, and any axis row): the proofs
    sharing the base of the row's last proof before that failure, and the proofs before them in a chain (an axis
    proof's base is the download after the visit before, so its attempt goes back proof by proof to the one whose base
    is the attempt's start, or to a visit that put its row back, which ended an attempt before), unless that attempt
    had already ended (a list row's last proof changed nothing; an axis row's last proof is its put-back, even one that
    left a record differing). Only the last failure's proof used to go: session A's two Focus Area / Custom 1
    attempts each stopped at Custom 3, and their Custom 2 visits, which wrote what Custom 2's registered frame loaded
    (two values in two attempts), counted (2026-11-08)."""
    out = {i for i, r in enumerate(proofs) if r.get("attempt") and r["attempt"] not in done}
    for k, frames in failing.items():
        legacy = [(i, r) for i, r in enumerate(proofs) if not r.get("attempt") and fail_key(r) == k]
        for frame in sorted(frames) if isinstance(frames, (list, tuple, set)) else [frames]:
            before = [(i, r) for i, r in legacy if proof_frame(r) < frame]
            if not before:
                continue
            base = max(before, key=lambda x: proof_frame(x[1]))[1].get("base")
            group = [(i, r) for i, r in legacy if r.get("base") == base]
            last = max(group, key=lambda x: proof_frame(x[1]))[1]
            # an axis put-back ends its attempt even when it left a record differing (explained, not failed, since
            # 2026-11-07); a list row's last proof with changes is a sticky side effect, and that attempt never ended
            ended = bool(last.get("final")) if last.get("kind") == "axis" else \
                not last.get("changes") and (last.get("final") or last.get("kind") in ("list", "dialog"))
            if ended and proof_frame(last) < frame:
                continue                 # that attempt ended as it began; the failure came after it
            by_dat = {r.get("dat"): (i, r) for i, r in before if r.get("dat")}
            prev, chain = by_dat.get(base), set()
            while prev is not None and not prev[1].get("final") and prev[0] not in chain:
                chain.add(prev[0])
                prev = by_dat.get(prev[1].get("base"))
            out |= {i for i, _ in group} | chain
    return out


def rows_of(run: Path, proofs: list | None = None, skip: set = frozenset()) -> dict:
    """row name -> {index: proof}, the latest proof per option; each number field its own row (its proofs leave
    the other fields as they were). skip: indices into proofs that do not count (unfinished).
    An index is a place in the list as the session that walked it numbered it: a list or a carousel's axis numbered
    from where it stood, a hold's list in another session, so two sessions can give one index to two options (hold
    2's Shoot Mode chose Aperture Priority and, in another session, Manual Exposure at place 3; S&Q's PAL rates, Drive
    Mode's speeds). The later proof of another option at an index taken (its label another, as norm reads it) is that
    option's latest where the row holds it at another index, and else goes under (index, label), the earlier proof
    kept (option_key): before 2026-11-11 it took the other option's place, and options of the a1 II's pass 2 lost
    their proof so, the two hold values among them kept only from an older definition. A number field's index is its
    value, the same option whatever its label shows of the other fields."""
    proofs = proofs_of(run) if proofs is None else proofs
    rows = collections.defaultdict(dict)
    for i, r in enumerate(proofs):
        if i in skip:
            continue
        opts = rows[row_name(r)]
        opts[option_key(r, opts)] = r
    return rows


def option_key(r: dict, opts: dict):
    """The key of proof r among its row's options (rows_of): its index; where another option's proof holds that index
    already (a number field's never), the key its own option has at another index, else (index, label)."""
    idx = tuple(r["index"]) if isinstance(r.get("index"), list) else r.get("index")
    have, lab = opts.get(idx), norm(str(r.get("label")))
    if r.get("kind") == "fields" or have is None or norm(str(have.get("label"))) == lab:
        return idx
    return next((k for k, o in opts.items() if norm(str(o.get("label"))) == lab), (idx, lab))


def not_one_to_one(proofs: list, row: str, key: str, vals: dict, kinds: set, carried: frozenset = frozenset(),
                   label_of: dict | None = None) -> list:
    """Notes for a record whose labels and values do not map one to one in a row: a label seen writing two values
    (in any attempt), or, in a list row whose options write only this record, two labels writing one value. Tables and
    carousels' axes too; a picker's twins (one function listed twice, label_of: index -> its name with "(2)") are told
    apart by their place in the list, and a value carried over from the option before (carried: (dat, key)) is not
    the label's."""
    notes = []
    if kinds & {"list", "dialog", "sidelist", "table", "axis"}:
        wrote = collections.defaultdict(set)
        for r in proofs:
            if row_name(r) != row or r.get("applied") is False or r.get("planned") is False or r.get("final"):
                continue
            idx = tuple(r["index"]) if isinstance(r["index"], list) else r["index"]
            # a picker's function by its place in the list, also in an attempt the report leaves out
            lab = (label_of.get((idx, norm(str(r.get("label"))))) or label_of.get(idx) or f"{r.get('label')} (place {idx})") \
                if label_of else str(r.get("label"))          # an option kept apart at a taken index (option_key)
            for c in element_changes(r):
                if c["key"] == key and (r.get("dat"), key) not in carried:
                    wrote[lab].add(json.dumps(c["after"]))
        for lab, vs in sorted(wrote.items()):
            if len(vs) > 1:
                notes.append({"value": None, "camera": lab, "schema": None, "kind": "not one to one",
                              "why": f"the label wrote {len(vs)} different values"})
    return notes


def picker_names(opts: dict) -> dict:
    """{index: name} for a function picker's options (picker_label), a name two places in the list share told apart by
    its place: "• AEL hold" at 42 and 44 is "AEL hold" and "AEL hold (2)", so twins never share one label for two
    proved values and the last proof does not win silently."""
    if not any(o["kind"] == "table" and o.get("opens") == "picker" for o in opts.values()):
        return {}
    named = {i: picker_label(o) for i, o in opts.items() if o["kind"] == "table" and o.get("opens") == "picker"}
    by_name = collections.defaultdict(list)
    for i, lab in named.items():
        by_name[norm(lab)].append(i)
    out = {}
    for idxs in by_name.values():
        for n, i in enumerate(sorted(idxs, key=lambda i: (isinstance(i, tuple), i))):
            out[i] = named[i] + (f" ({n + 1})" if n else "")
    return out


def carried_over(proofs: list, skip: set = frozenset()) -> list:
    """Values a record kept from the option before while other records of the same proof moved: [{row, key, label,
    value, dat}]. Within one attempt of a list, carousel or table row (proofs in order), when an option's proof shows a
    record holding exactly what the previous option's proof wrote to it, and some other record moved between the two,
    the camera left that record as it was (ISO AUTO Maximum following Minimum, a hold's speed kept under a bracket,
    the format flag 0x16ae kept from an HD format by the next one): the value is not this option's, and is not
    credited to its label. A record every option of the attempt leaves at one value is the row's own, never carried."""
    groups = collections.defaultdict(list)
    for i, r in enumerate(proofs):
        if i in skip or r.get("kind") not in ("list", "dialog", "sidelist", "table") or r.get("proof") == "display":
            continue
        groups[(row_name(r), r.get("attempt") or r.get("base"))].append(r)
    by_base = collections.defaultdict(list)          # every counted proof of a row, by its row without context or
    for i, r in enumerate(proofs):                    # option (a carousel option's axis proofs choose it too)
        if i not in skip and r.get("changes"):
            by_base[base_row(row_name(r))].append(r)
    out = []
    for (row, _), rs in groups.items():
        rs.sort(key=proof_frame)
        state = [{c["key"]: json.dumps(c["after"]) for c in element_changes(r)} for r in rs]
        values = collections.defaultdict(set)
        for st in state:
            for k in set().union(*state):
                values[k].add(st.get(k))          # None: the attempt's start value
        moved = [st for st in state if st]
        for n in range(1, len(rs)):
            prev, cur, r = state[n - 1], state[n], rs[n]
            if r.get("applied") is False or r.get("planned") is False:
                continue
            for k, v in cur.items():
                if prev.get(k) != v or len(values[k]) < 2:
                    continue
                # a shared value, not a kept one: the record has one value besides the start and every option that
                # moved anything wrote it (HEIF 4:2:0 and 4:2:2 alike, the movie family's records on Movie, S&Q
                # and Time-lapse); or another proof shows this option writing it from elsewhere
                if len(values[k] - {None}) == 1 and all(st.get(k) == v for st in moved):
                    continue
                if any(o.get("dat") != r.get("dat") and str(r.get("label")) in (str(o.get("label")),
                                                                               str(o.get("label")).split(":")[0])
                       and any(c["key"] == k and json.dumps(c["after"]) == v for c in element_changes(o))
                       for o in by_base.get(base_row(row), ())):
                    continue
                if any(prev.get(o) != cur.get(o) for o in set(prev) | set(cur) if o != k):
                    out.append({"row": row, "key": k, "label": str(r.get("label")), "value": json.loads(v),
                                "dat": r.get("dat")})
    return out


def two_labels_one_value(opts: dict, recs: dict) -> dict:
    """{key: [labels]} for a list row whose options write one record only: two options seen writing one value."""
    if len(recs) != 1 or not all(o["kind"] == "list" for o in opts.values()):
        return {}
    (key, _), = recs.items()
    by_value = collections.defaultdict(list)
    for o in opts.values():
        if o.get("applied") is False or o.get("planned") is False:
            continue
        for c in element_changes(o):
            if c["key"] == key:
                by_value[json.dumps(c["after"])].append(str(o["label"]))
    clash = [labs for labs in by_value.values() if len(labs) > 1]
    return {key: sorted(set(sum(clash, [])))} if clash else {}


def linear(vals: dict):
    """For sampled number fields: does the stored value follow the shown number on a straight line
    through the lowest and highest? None when it cannot be told (under three numbers). The keys may be the numbers
    themselves (scale_line, grid_lines)."""
    pts = sorted({(n, v) for lab, v in vals.items()
                  if isinstance(v, (int, float)) and (n := lab if isinstance(lab, (int, float)) else num(lab)) is not None})
    if len(pts) < 3 or pts[-1][0] == pts[0][0]:
        return None
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    return all(abs(y0 + (y1 - y0) * (x - x0) / (x1 - x0) - y) < 1e-6 for x, y in pts)


def num(t):
    """The number in a label, with its sign ("-15", "+7", "92.5%", "02"); None for text."""
    m = re.fullmatch(r"\s*([+-]?)\s*(\d+(?:\.\d+)?)\s*%?\s*", str(t or ""))
    return None if not m else float(m.group(2)) * (-1 if m.group(1) == "-" else 1)


# a number on a scale as the camera shows it: an option's name in front ("C.Temp./Filter: 6000 K"), a sign, ± for zero,
# a signed fraction ("+5/6", a scale around zero), and one unit of the few a scale is counted in (Kelvin, EV, percent); a
# frame rate ("60p") or a shutter speed ("1/250", no sign) is no scale, and is left alone
SCALE_NUMBER = re.compile(r"\s*([+\-±]?)\s*(\d+(?:\.\d+)?)(?:\s*/\s*(\d+))?\s*(K|EV|%)?\s*")
SCALE_SIGNS = str.maketrans({"−": "-", "‡": "±"})


def scale_number(t) -> tuple | None:
    """(number, unit) of a label on a number scale (SCALE_NUMBER): "С.Temp./Filter: 6000 K" is (6000.0, "K"), "+2/6" is
    (0.333..., ""), "±0" (0.0, ""), "-0.3 EV" (-0.3, "EV"); None for any other text. Read after the last ": ", so an
    option's name in front and OCR's Cyrillic letters in it do not matter."""
    text = str(t or "").translate(LOOKALIKE).translate(SCALE_SIGNS).rsplit(": ", 1)[-1]
    m = SCALE_NUMBER.fullmatch(text)
    if not m or (m.group(3) and (int(m.group(3)) == 0 or not m.group(1))):
        return None
    n = float(m.group(2)) / (int(m.group(3)) if m.group(3) else 1)
    return n * (-1 if m.group(1) == "-" else 1), m.group(4) or ""


def scale_line(vals: dict):
    """A sampled list or carousel axis of numbers in one unit (scale_number): does the stored value follow the shown
    number on a straight line through the lowest and highest (linear)? None when the labels are not such numbers, or
    under three of them. KIT_PLAN's line rule ("Sampling long number ranges") for the scales a menu lists, not types:
    White Balance's colour temperature, Exposure Std. Adjust's sixths, Aspect Marker Level."""
    read = {lab: scale_number(lab) for lab in vals}
    if any(r is None for r in read.values()) or len({r[1] for r in read.values()}) != 1:
        return None
    return linear({r[0]: vals[lab] for lab, r in read.items()})


def element_changes(o) -> list:
    """An array record (one slot per Picture Profile) changes in one slot: "global:0x04e9[0]", the
    schema's key for that slot, with that slot's values. A single-option list's display proof (prove_run's
    "proof": "display") changes nothing: each record it names "held" is taken as written with the value it holds,
    so its label is seen writing that value, as a proof by choosing would show it."""
    if o.get("proof") == "display":
        return [{"key": h["key"], "before": h["value"], "after": h["value"]} for h in o.get("held") or []]
    # a My Menu add (kit/provers/mymenu_run.py) names the slot it filled: only that slot's change is the item's
    only = (o.get("my_menu") or {}).get("slot")
    out = []
    for c in o["changes"]:
        if isinstance(c["before"], list) and isinstance(c["after"], list):
            out += [{"key": f"{c['key']}[{i}]", "before": a, "after": b}
                    for i, (a, b) in enumerate(zip(c["before"], c["after"], strict=True)) if a != b and (only is None or i == only)]
        else:
            out.append(c)
    return out


def readout(axis: str, v: int) -> str:
    """The grid's own words for a fine-tune value in the prover's convention (A and G below zero):
    -7000 on A-B is "A7", 1250 on G-M is "M1.25"."""
    neg, pos = ("A", "B") if axis == "A-B" else ("G", "M")
    return "0" if v == 0 else f"{neg if v < 0 else pos}{abs(v) / 1000:g}"


def grid_values(opts: dict) -> dict:
    """White Balance fine-tune: per record, the grid's readout (as the screen showed it) -> the value
    stored. The last visit of each axis puts it back: its readout is the value before."""
    out = {}
    for o in opts.values():
        if o["axis"] == "corner" or o["index"][-1] == "back":
            continue                          # corners: checked by grid_independence
        lab = readout(o["axis"], o["value"])
        for c in o["changes"]:
            out.setdefault(c["key"], {})[lab] = c["after"]
    for o in opts.values():
        if o["index"][-1] == "back":
            for key, vals in out.items():
                first = next(c["before"] for oo in opts.values() for c in oo["changes"] if c["key"] == key)
                if o["axis"] != "corner" and any(oo["axis"] == o["axis"] for oo in opts.values()
                                                 if any(c["key"] == key for c in oo["changes"])):
                    vals.setdefault(readout(o["axis"], o["value"]), first)
    return out


def grid_groups(proofs: list) -> dict:
    """White Balance grid proofs by (preset, context): Movie mode keeps a grid of its own for most presets (0x0e9b
    beside the stills 0x0e99) and writes the record in use (0x0c4d) from another start, so a preset's corners are
    checked against its own context's axes only. (preset, context) -> the proofs, the put-back visits left out."""
    out = collections.defaultdict(list)
    for r in proofs:
        if r.get("kind") == "wbgrid" and r["index"][-1] != "back":
            out[(r["preset"], r.get("context") or "")].append(r)
    return dict(sorted(out.items(), key=lambda kv: (kv[0][0], kv[0][1])))


def grid_lines(proofs: list) -> dict:
    """Each White Balance grid record's line rule in each (preset, context): the grid position each visit chose
    (an axis's ends and 0, and on the corners and the inside point that axis's coordinate) against what the record
    stored. {(preset, context, key): linear(...)}: True when every point lies on the straight line through the
    lowest and highest position, None under three positions (KIT_PLAN, "Sampling long number ranges")."""
    out = {}
    for (P, ctx), rs in grid_groups(proofs).items():
        axis_of, pts = {}, collections.defaultdict(dict)
        for r in rs:
            if r["axis"] in ("A-B", "G-M"):
                for c in element_changes(r):
                    axis_of[c["key"]] = r["axis"]
                    pts[c["key"]][r["value"]] = c["after"]
        for r in rs:
            if r["axis"] == "corner":
                ab, gm = r["value"]
                for c in element_changes(r):
                    if c["key"] in axis_of:
                        pts[c["key"]][ab if axis_of[c["key"]] == "A-B" else gm] = c["after"]
        for key, p in pts.items():
            out[(P, ctx, key)] = linear(p)
    return out


def grid_independence(run: Path) -> list:
    """White Balance grids: each corner (and the inside point) must store, on each axis's records,
    what the straight line through that axis's own proofs (both ends and 0) gives, within one preset's context
    (grid_groups: a stills corner says nothing of the Movie grid's records). One line per preset and context:
    (preset with its context, corners checked, mismatches)."""
    out = []
    for (P, ctx), rs in grid_groups(jsonl.read(run / "proofs.jsonl")).items():
        cross = [r for r in rs if r["axis"] in ("A-B", "G-M")]
        lines = {}                                  # record -> (axis, {position: stored})
        for r in cross:
            for c in element_changes(r):
                lines.setdefault(c["key"], (r["axis"], {}))[1][r["value"]] = c["after"]
        corners = [r for r in rs if r["axis"] == "corner"]
        bad = []
        for r in corners:
            ab, gm = r["value"]
            got = {c["key"]: c["after"] for c in element_changes(r)}
            for key, (axis, pts) in lines.items():
                x = ab if axis == "A-B" else gm
                if len(pts) < 2:
                    continue
                (x0, y0), (x1, y1) = min(pts.items()), max(pts.items())
                want = round(y0 + (y1 - y0) * (x - x0) / (x1 - x0))
                if got.get(key) != want and not (want == 0 and key not in got):
                    bad.append((ab, gm, key, want, got.get(key)))
        if corners:
            out.append((f"{P} [{ctx}]" if ctx else P, len(corners), bad))
    return out


def axis_values(opts: dict, own: dict | None = None, names: dict | None = None,
                main_keys: frozenset | None = None) -> dict:
    """A carousel option's second axis: every proof also chose the option itself, so a record that
    took the same value in all of them is the option's own (proved with the carousel); the records
    that differ between axis values are the axis's, labelled by axis value. The last visit put the
    axis back on the value it held: that value's number is the records' value before.
    A two-value axis has one test, where nothing can differ: there the option's own records are the
    ones the carousel's own proof of the option wrote, with the same value (`own`, key -> value;
    WB / DRO Bracket Hi, whose 0x04ca / 0x04cc had been dropped, 2026-10-31).
    The value the axis held is credited to the last visit's label, as a list's own start is (the playbook, "Seen, or
    inferred": one option per row), on a record only the axis writes: none the carousel's own row wrote with any of
    its options, and no live readout (main_keys; Focus Area's full-memory records hold the option the carousel opened
    on as well as the axis value, so their value before is no axis value), and only when no other label of the axis
    was seen writing that value. Unknown main row (main_keys None): no credit."""
    tests = [o for o in opts.values() if not o.get("final") and o.get("applied") is not False]
    final = next((o for o in opts.values() if o.get("final")), None)
    keys = {c["key"] for o in tests for c in o["changes"]}
    out = {}
    for key in keys:
        got = {o["label"]: next((c["after"] for c in o["changes"] if c["key"] == key), None) for o in tests}
        before = next(c["before"] for o in tests for c in o["changes"] if c["key"] == key)
        filled = {lab: (before if v is None else v) for lab, v in got.items()}
        if len(tests) == 1:
            row = tests[0]["path"][-1] if tests[0].get("path") else None
            if row and names and names.get(key) == row:
                continue                              # a record the schema names after the carousel itself
            if own is None or (key in own and str(own[key]) == str(next(iter(filled.values())))):
                continue                              # the option's own record (or nothing to tell by)
        elif len(set(map(str, filled.values()))) <= 1:
            continue                                  # the option's own record, not the axis's
        # the last visit proves everything went back; on the records the carousel's own options write too, its value
        # is the option the carousel opened on, not the axis value held (Focus Area's full-memory records hold both),
        # so no label there
        out[key] = {lab: v for lab, v in got.items() if v is not None}
        held = held_axis_value(tests, final, key, out[key], main_keys)
        if held is not None:
            out[key][final["label"]] = held
    return out


def held_axis_value(tests: list, final: dict | None, key: str, seen: dict, main_keys: frozenset | None):
    """The value the axis held when its proofs began, for the last visit's label (axis_values): the record's value
    before in the visits of the last visit's own attempt (its base file), when they agree, else the value that base
    file holds (base_value), never another attempt's start; None when the last visit did not put everything back, the
    record is one the carousel's own row writes or a live readout (main_keys; or that row is unknown), or another
    label was seen writing the value."""
    if final is None or main_keys is None or key in main_keys or final.get("applied") is False or final.get("changes") \
            or final.get("label") in seen:
        return None
    same = [o for o in tests if o.get("base") == final.get("base")]
    befores = {json.dumps(c["before"]) for o in same for c in o["changes"] if c["key"] == key}
    if not same:                                # no visit of the last visit's own attempt: read its base file
        v = base_value(final.get("base"), key)
        befores = set() if v is None else {json.dumps(v)}
    if len(befores) != 1:
        return None
    before = json.loads(befores.pop())
    return None if before in seen.values() else before


# the display mode in use, monitor and finder: the ILCE-1M2's record ids, emptied for another body's run (main).
# TODO: into data/<model>_fw<fw>/camera_*.json (docs/decisions/0019, 0020)
DISP_MODES = {"global:0x04e5", "global:0x04e6"}


def check_values(opts: dict, elsewhere: frozenset = frozenset(), names: dict | None = None) -> dict:
    """A checklist: each visit flips one box (and puts the previous one back), so a record changed in
    visit i belongs to box i: "<box>: ticked" -> its value after, the other state -> before.
    Records every one-box visit changed are written by OK itself, not by the box. A box proved
    together with another ("together_with": the camera refused it alone) leaves out the other box's
    own records, and takes the records written on OK whose value it alone changed (Rating Set: the
    1-star box's second copy, 0 until the screen is first saved)."""
    vis = [o for o in opts.values() if o.get("applied") is not False
           and any(b["box"] == o["index"] for b in o.get("boxes") or [])]
    # DISP Set: the display mode in use moves when its box is unticked; it is not a box's record
    vis = [{**o, "changes": [c for c in o["changes"] if c["key"] not in DISP_MODES]}
           if o["path"][0].startswith("DISP") else o for o in vis]
    own = {o["index"]: {c["key"] for c in o["changes"]} for o in vis if not o.get("together_with")}
    on_ok = set.intersection(*own.values()) if len(own) >= 2 else set()
    # a box's own records change in its own visit only: the run's next visit puts the box back, so a
    # record still changed then moved with something else (the focus area in use when its cell is
    # unticked, Focus Area Limit 2026-10-30; it stays after the cell is ticked again)
    by_base = collections.defaultdict(list)
    for o in opts.values():
        if not o.get("together_with"):
            by_base[o.get("base")].append(o)
    still = {}
    for rs in by_base.values():
        rs.sort(key=lambda o: o["index"])
        for a, b in zip(rs, rs[1:]):  # noqa: B905 (pairs each run with next)
            still[(a.get("base"), a["index"])] = {c["key"] for c in b["changes"]}
    out = {}
    # copies of a box's tick the prover told apart (prove_run.mirrored_boxes, Rating Set(Custom Key)'s second
    # copies, 2026-11-07): each is its box's, ticked and unticked, whatever visit moved it
    mirrors = {k: m for o in opts.values() for k, m in ((PUT_BACK.get(o.get("attempt")) or {}).get("mirrors") or {}).items()}
    for key, m in mirrors.items():
        out[key] = {f"{m['box']}: ticked": m["ticked"], f"{m['box']}: unticked": 1 - m["ticked"]}
    for o in vis:
        box = next(b for b in o["boxes"] if b["box"] == o["index"])
        now = "ticked" if box["ticked"] else "unticked"
        was = "unticked" if box["ticked"] else "ticked"
        skip = set(on_ok) | set(elsewhere) | set(mirrors) | \
            (still.get((o.get("base"), o["index"]), set()) if not o.get("together_with") else set())
        # a visit that changed a record the schema names for this row ("Focus Area Limit: Wide") keeps
        # that one; the rest moved with the setting in use (spot size, Free Size slot, 2026-10-30)
        named = {c["key"] for c in o["changes"] if (names or {}).get(c["key"], "").startswith(o["path"][-1] + ":")}
        if named:
            skip |= {c["key"] for c in o["changes"]} - named
        if o.get("together_with"):
            skip |= {k for b in o["boxes"] if b["box"] != o["index"] for k in own.get(b["box"], set())}
        for c in o["changes"]:
            if c["key"] not in skip and box.get("radio"):
                # a radio sub-option (DISP Set's Exposure: On / TimeOut): its value and its partner's
                out.setdefault(c["key"], {})[box["label"] if box["ticked"] else box["radio"]] = c["after"]
                out[c["key"]][box["radio"] if box["ticked"] else box["label"]] = c["before"]
            elif c["key"] not in skip:
                out.setdefault(c["key"], {})[f"{box['label']}: {now}"] = c["after"]
                out[c["key"]][f"{box['label']}: {was}"] = c["before"]
        if o.get("together_with"):
            left = {c["key"] for c in o["changes"]}
            for key in on_ok - left:
                ch = [c for s in vis if s["index"] in own for c in s["changes"] if c["key"] == key]
                if len({c["after"] for c in ch}) == 1:
                    out.setdefault(key, {})[f"{box['label']}: {was}"] = ch[0]["after"]
                    out[key][f"{box['label']}: {now}"] = ch[0]["before"]
    return out


# records only some of a row's options write: a Recall Custom hold keeps its continuous speed when a
# bracket or Single Shooting is registered (2026-10-31), so the other options say nothing about it. The ILCE-1M2's
# record id, emptied for another body's run (main). TODO: into data/<model>_fw<fw>/camera_*.json (decisions 19, 20)
WRITTEN_BY = {"global:0x0bf1": re.compile(r"^Cont\. Shooting")}
# AF Area Registration's Tracking start area copies (kit/provers/afreg_run.py): a Tracking area's hold writes its start
# area; any other area's hold copies the live Tracking start area, the camera's own setting and no value of that area,
# which the prover keeps out of the proof's changes (2026-11-09). Its lines name those copies in "side_effects" since
# 2026-11-09, which values_of never credits (side_named, any body); this rule keeps the a1 II's earlier lines, which
# named only the copies that changed, from crediting an unchanged copy to a non-Tracking area
WRITTEN_BY.update({f"global:0x{rid:04x}": re.compile(r"^Tracking:")
                   for rid in (0x0e74, 0x0e76, 0x0e78, 0x0f8c, 0x0f8e, 0x0f90)})


_BASE_DIRS: list = []          # where the proofs' base files are (main: <run>/dat and <run>)
_RUNS_ROOT: list = []          # the camera's runs, where a base named with its run is (qualified; main fills it)
_BASE_CACHE: dict = {}


def base_file(base: str) -> Path | None:
    """A proof's base file: one named with its run in front (qualified) in that run's dat/ or at its top, else in
    _BASE_DIRS (a bare name, or a path from there such as "../../kit2_dial/dat/00009_x.DAT"); None where there is
    none."""
    m = QUALIFIED.fullmatch(base)
    places = [r / m[1] / sub / m[2] for r in _RUNS_ROOT for sub in ("dat", "")] if m else []
    return next((p for p in places + [d / base for d in _BASE_DIRS] if p.exists()), None)


def base_value(base: str | None, key: str):
    """A record's value in a proof's base file, read from the file itself. An option that changed nothing is
    credited with the value its own session started from; `befores` knows only the bases of proofs that changed
    the record, so a put-back made in a session of its own (the saved option alone, 2026-11-07: Fn Menu's "Follow
    Still Fnct Menu" credited with the October session's 935 instead of its own 882) must read its base."""
    if not base or not (_BASE_DIRS or _RUNS_ROOT):
        return None
    m = re.fullmatch(r"(global|set(\d+)):0x([0-9a-f]{4})(?:\[(\d+)\])?", key)
    if not m:
        return None
    path = base_file(base)
    if path is None:
        return None
    cs = _BASE_CACHE.get(path)                # by the file found: two runs may hold files of one name
    if cs is None:
        try:
            cs = _BASE_CACHE[path] = camset.read(path)
        except (ValueError, OSError):
            return None
    r = cs.get(0 if m.group(1) == "global" else int(m.group(2)), int(m.group(3), 16))
    if r is None:
        return None
    v = r.value()
    if m.group(4) is None:
        return v
    i = int(m.group(4))              # one slot of the record, as element_changes keys it
    return v[i] if isinstance(v, list) and i < len(v) else None


def screen_records(opts: dict, carried: frozenset = frozenset()) -> set:
    """The records only picker functions with a screen of their own wrote (values carried over from them aside): that
    screen's doing, not the key's (a Recall Custom hold's registration copies the hold into the working slot 0x18cb[3]
    and its kin, Rating Set writes its copies, 2026-11-07). The record the other functions write, the key's own, is
    credited as for any function; these are credited to nothing and raise no question when carried over."""
    if not any(o.get("own_screen") for o in opts.values()):
        return set()
    plain = {c["key"] for o in opts.values() if not o.get("own_screen") for c in element_changes(o)
             if (o.get("dat"), c["key"]) not in carried}
    return {c["key"] for o in opts.values() if o.get("own_screen") for c in element_changes(o)} - plain


def values_of(opts: dict, elsewhere: frozenset = frozenset(), names: dict | None = None,
              own: dict | None = None, inferred: dict | None = None, carried: frozenset = frozenset(),
              sources: dict | None = None, disputes: dict | None = None, kept_over: frozenset = frozenset(),
              main_keys: frozenset | None = None, held_back: dict | None = None) -> dict:
    """record key -> {label: value}. The option a row started on changes nothing: its value is the
    one every other option's change started from. Each label is name_of's; sources (key -> {label: source}) and
    disputes ((key, label) -> {label, shown, vlm, frame}) are filled when given. A value carried over from the option
    before (carried: (dat, key), carried_over) is not credited to the label. kept_over: every value carried over,
    those a hand rule names too, which no plain option wrote when the records a function's own screen writes are
    told apart (screen_records). main_keys: on a carousel's axis row, the records no held value is credited on
    (axis_values): those the carousel's own row wrote, and the live readouts. held_back (key -> {label: value}), when
    given, gets each value a start line (start_lines: a list walked in part, its session's first sight or last choice
    back on the start) would have credited: no proof of the label, only what the session's start held (decision 16)."""
    twins = picker_names(opts)
    starts = start_lines(opts)
    # a table walked whole but for its start, which only the put-back line chose ("planned": false): the start is one
    # option among all of them there, credited from that line as a whole walk's own start is; left out, it would be
    # the slot's one value named from elsewhere among values its readers named (decision 16)
    whole_table = whole_but_start(opts)
    opts = {i: {**o, "changes": [c for c in element_changes(o) if c["key"] not in side_kept(o)]} for i, o in opts.items()}
    screens = screen_records(opts, carried | kept_over)
    if screens:
        opts = {i: {**o, "changes": [c for c in o["changes"] if c["key"] not in screens]} for i, o in opts.items()}
    if any(o["kind"] == "checklist" for o in opts.values()):
        return check_values(opts, elsewhere, names)
    if any(o.get("family_of") for o in opts.values()):
        # Shoot Mode's family (kit/provers/shootmode_run.py): switching to Movie also loads the records Different
        # Set keeps per mode (ISO, White Balance, Picture Profile...), which belong to their own rows
        # (ISO AUTO Max in use too, 2026-10-30): only the records about the family are the family's
        fam = re.compile(r"family|S&Q mode active", re.I)
        opts = {i: {**o, "changes": [c for c in o["changes"] if c["key"] not in elsewhere
                                     and fam.search((names or {}).get(c["key"], ""))]} for i, o in opts.items()}
    if any(o["kind"] == "lookbase" for o in opts.values()):
        # a custom look's base: changing it also resets the slot's parameters to that look's own
        # (Fade, Sharpness, Clarity, 2026-10-30); only the Base Look record is the row's
        opts = {i: {**o, "changes": [c for c in o["changes"] if (names or {}).get(c["key"], "").startswith("Base Look")]}
                for i, o in opts.items()}
    if any(o.get("boxes") is True for o in opts.values()):
        # two boxes on one screen (ISO AUTO Minimum / Maximum): the camera keeps Minimum <= Maximum, so
        # a box pushes the other's records too (Maximum follows Minimum up, 2026-11-01). A box's own
        # records follow every visit; one that took fewer than half as many values moved with the other
        moved = collections.defaultdict(set)
        for o in opts.values():
            for c in o["changes"]:
                moved[c["key"]].add(json.dumps(c["after"]))
        most = max((len(v) for v in moved.values()), default=0)
        opts = {i: {**o, "changes": [c for c in o["changes"] if 2 * len(moved[c["key"]]) >= most]}
                for i, o in opts.items()}
    if any(o["kind"] == "axis" for o in opts.values()):
        return axis_values(opts, own, names, main_keys)
    if any(o["kind"] == "wbgrid" for o in opts.values()):
        return grid_values(opts)
    keys = {c["key"] for o in opts.values() for c in o["changes"]}
    # a record another row's proofs own (elsewhere) that every option of this row that changed anything wrote to one
    # value moved with the state the first option put the camera in, not with the options (S&Q Shoot Mode's proofs
    # both carry the S&Q exposure mode the camera set on entering S&Q Motion, 2026-11-07): not this row's
    moved = [o for o in opts.values() if o["changes"] and o.get("applied") is not False]
    if len(moved) >= 2:
        for key in list(keys):
            vs = {json.dumps(c["after"]) for o in moved for c in o["changes"] if c["key"] == key}
            if key in elsewhere and len(vs) == 1 and all(any(c["key"] == key for c in o["changes"]) for o in moved):
                keys.discard(key)
    out = {}
    for key in keys:
        before = next(c["before"] for o in opts.values() for c in o["changes"] if c["key"] == key)
        # a row proved in two runs has two starting values: an option that changed nothing holds its
        # own run's (Shooting Interval's home visit, in a run of its own, read the other run's start,
        # 2026-10-31)
        befores = {}
        for o in opts.values():
            for c in o["changes"]:
                if c["key"] == key:
                    befores.setdefault(o.get("base"), c["before"])
        written = {json.dumps(c["after"]) for o in opts.values() for c in o["changes"] if c["key"] == key}
        # a label seen to change the record outranks the same label taken from "nothing changed": a
        # visit can miss its option (Drive Mode's self-timer read "Single Shooting" after OK, 2026-10-31)
        vals, seen, src = {}, set(), {}
        for i, o in opts.items():
            ch = [c for c in o["changes"] if c["key"] == key]
            if o["kind"] == "fields":
                if o.get("applied") is None and "applied" in o:
                    continue                      # never seen again: which value applied is not known
                lab = o["kept"] if o.get("applied") is False else o["value"]
            else:
                if o.get("applied") is False:
                    continue                      # refused ("not available"): the value did not change
                if o.get("planned") is False and not whole_table:
                    continue                      # chosen only to put the saved one back: the user's own
                if (o.get("dat"), key) in carried:
                    continue                      # kept from the option before: not this option's value
            lab, how, dispute = name_of(o)
            lab = twins.get(i, lab)
            only = WRITTEN_BY.get(key.split("[")[0])
            if only is not None and not only.search(str(lab)):
                continue
            if not ch and {key, key.split("[")[0]} & side_named(o):
                continue                          # a record the proof names as a side effect: not its option's value
            if ch:
                vals[lab] = ch[0]["after"]
                seen.add(lab)
            elif lab not in seen:
                if o.get("my_menu"):
                    continue              # an add writes one slot; the other pages hold what earlier adds wrote
                if i in starts:
                    # the session's start or its put-back in a list walked in part: the value is what the start held,
                    # which would stand out among the options chosen (decision 16); counted as a "planned": false line
                    if held_back is not None:
                        v = befores.get(o.get("base"))
                        held_back.setdefault(key, {})[lab] = base_value(o.get("base"), key) if v is None else v
                    continue
                if key in elsewhere and len(written) == 1 and \
                        not (names or {}).get(key, "").startswith(own_name(o)):
                    # another row's record, which one option of this row pushed to one value as a side effect (ISO
                    # Auto/Manual Set = Auto puts ISO on AUTO, 2026-11-07): what it held before is that row's value,
                    # not this option's. A record this row's options take through several values is a setting of
                    # the row's (Tracking Shift Range, reached by two routes), and one the definition names for the
                    # row is its own though another row writes it too (S&Q Shoot Mode's, which the Shoot Mode
                    # carousel's family also sets; a setting table's cell by its row: File Format (Slot 1), which
                    # JPEG/HEIF Switch also writes, is the File Format cell's)
                    continue
                v = befores.get(o.get("base"))
                if v is None:
                    v = base_value(o.get("base"), key)
                vals[lab] = before if v is None else v
            else:
                continue
            src[lab] = how
            if disputes is not None:
                if dispute:
                    disputes[(key, lab)] = {**dispute, "frame": o.get("chosen_frame")}
                else:
                    disputes.pop((key, lab), None)
        out[key] = vals
        if sources is not None:
            sources[key] = src
        # labels no visit was seen to write: one is the row's own start; with two or more, all but
        # one were taken from "nothing changed" on a visit to another option
        unseen = [lab for lab in vals if lab not in seen]
        if inferred is not None and len(unseen) >= 2 and not any(o["kind"] == "fields" for o in opts.values()):
            inferred[key] = sorted(unseen)
    return out


def scale_verdict(opts: dict, kinds: set, key: str, vals: dict, s: dict | None, lines: dict):
    """A record's line rule (KIT_PLAN, "Sampling long number ranges"), or None where it does not apply:
    - a sampled number field or side list (or one proved at every value, --every): its numbers (linear); the
      definition keeps such a record as "sampled" either way, and "None" would read as too few;
    - a list or a carousel axis of numbers in one unit (scale_line) that sampled the definition's longer list (the
      colour temperature's 4 of 75): its numbers; a list proved whole is no sample, whatever its numbers;
    - a White Balance grid: its positions against what it stored, the corners and inside point included (grid_lines).
    """
    if any(o.get("sampled") for o in opts.values() if o["kind"] != "wbgrid") or kinds & {"sidelist", "fields"}:
        return linear(vals) if all(num(lab) is not None for lab in vals) else None
    if "wbgrid" in kinds:
        o = next(o for o in opts.values() if o["kind"] == "wbgrid")
        return lines.get((o["preset"], o.get("context") or "", key))
    if kinds <= {"list", "dialog", "axis"} and s and len(s.get("values") or []) > len(set(map(str, vals.values()))):
        return scale_line(vals)
    return None


def main_row_keys(rows: dict, name: str, opts: dict) -> frozenset | None:
    """An axis row's carousel, as its own rows proved it: every record any of its options wrote in any state (axis_values;
    Metering Mode's Movie record 0x0e08 is written by Movie mode's own row, Drive Mode's copy 0x13d4 by the recheck's),
    the carousel's axis rows left out. None for a row that is no axis's, or a carousel whose own rows have no proofs."""
    if not any(o["kind"] == "axis" for o in opts.values()):
        return None
    mains = [r for row, r in rows.items() if base_row(row) == base_row(name)
             and not any(o["kind"] == "axis" for o in r.values())]
    if not mains:
        return None
    return frozenset(c["key"] for main in mains for o in main.values() if o.get("applied") is not False
                     for c in element_changes(o))


def dat_number(name: str | None) -> int:
    """A proof's download number, the order the session took it in ("187886_Gamma-7.DAT", "kit2_afreg2/00054_x.DAT")."""
    m = re.match(r"(?:.*/)?(\d+)", name or "")
    return int(m[1]) if m else -1


def own_name(o: dict) -> str:
    """The name of the row a proof sets, as a record named for it starts: its menu row, or a setting table's cell's row
    ("File Format" of "Image Quality Settings / File Format / SLOT 1"), its context aside."""
    if o.get("kind") == "table" and o.get("screen", "table") == "table" and o.get("option"):
        return str(o["option"]).rpartition(" / ")[0] or str(o["option"])
    return str(o["path"][-1]).split(" [")[0]


def start_lines(opts: dict) -> frozenset:
    """The options of a list or side-list row walked only in part whose proof line is its session's first sight of the
    row or its last choice (a session: the lines diffed against one base, the start download, in download order): the
    option the camera held, chosen to start from or to put it back. Such a line changes nothing, so the value it would
    credit is only what the start held; in a part walk it would stand out among the options chosen, the camera's own
    setting (decision 16), and it is credited to nothing, as a "planned": false line is not. A row walked whole (every place of its list chosen,
    from the first to the farthest, refused ones included) keeps its start: there it is one option among all of them.
    Carousels, dialogs, axes and tables go by their own rules (a table sampled from the start: sampled_from_start)."""
    if not opts or any(o["kind"] not in ("list", "sidelist") for o in opts.values()):
        return frozenset()
    places = {i for i in opts if isinstance(i, int)}
    if not places or places == set(range(max(places) + 1)):
        return frozenset()
    sessions = collections.defaultdict(list)
    for i, o in opts.items():
        sessions[o.get("base")].append((dat_number(o.get("dat")), i))
    return frozenset(x for lines in sessions.values() for x in (min(lines)[1], max(lines)[1]))


def whole_but_start(opts: dict) -> bool:
    """A table row whose lines chose every place of its list from the first to the farthest, the start among them only
    as the put-back line ("planned": false): a whole walk, its start one option among all of them, which values_of
    credits from that line as a whole walk's own start is. A short row, or one with a place no line chose, is no such
    walk: its put-back stays uncredited."""
    if not opts or any(o["kind"] != "table" for o in opts.values()) or sampled_from_start(opts):
        return False
    places = {i for i, o in opts.items() if isinstance(i, int) and o.get("applied") is not False}
    return len(places) > 3 and places == set(range(max(places) + 1))


def sampled_from_start(opts: dict) -> bool:
    """A table row whose proofs visited fewer than half of the places up to the farthest one: a sample that started
    from the option the camera held. A table cell's list is numbered from the option it opened on, the one the camera
    held (kit/table_walk.py, walk_options), so a row that chose only some of its places stepped from that option a
    fixed way, and whoever knows the camera's list could tell the held option from the values it proves
    (docs/decisions/0016). A walk of the whole list leaves out only the few functions with a screen of their own; the
    put-back (planned false) counts as no visit. The values stay in this report; kit/schema_update.py writes such a
    record's proof as a count ("sampled", "from_start")."""
    if not opts or any(o["kind"] != "table" for o in opts.values()):
        return False
    places = {i for i, o in opts.items() if isinstance(i, int) and o.get("applied") is not False
              and o.get("planned") is not False}
    return bool(places) and max(places) + 1 > 3 and 2 * len(places) < max(places) + 1


def no_credit(rows: dict, name: str, opts: dict, readouts: frozenset) -> frozenset | None:
    """The records an axis row credits no held value on (axis_values' main_keys): those the carousel's own row writes
    (main_row_keys) and the live readouts (a setting whose note says "view only": ISO in use holds the start's ISO,
    never the axis's value). None, no credit at all, for a row that is no axis's or whose carousel has no proofs."""
    mains = main_row_keys(rows, name, opts)
    return None if mains is None else mains | readouts


def own_records(rows: dict, name: str, opts: dict) -> dict | None:
    """An axis row's option, as the carousel's own row proved it: key -> value it wrote."""
    option = next((o.get("option") for o in opts.values() if o["kind"] == "axis"), None)
    if not option:
        return None
    # the carousel's own row in the same context, else without one (an axis proved again in a
    # switched state: WB / DRO Bracket held on Hi by a file, 2026-10-31)
    main = rows.get(re.sub(r" / [^\[]*", "", name, count=1).rstrip()) or rows.get(base_row(name))
    if not main:
        return None
    return {c["key"]: c["after"] for o in main.values() if str(o.get("label", "")).startswith(option)
            and o.get("applied") is not False for c in element_changes(o)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("run", nargs="?", default="kit2_pass2", type=paths.run_arg,
                    help="the proofs' run (a run in the camera's runs/<model>_fw<fw>/, or a path)")
    ap.add_argument("--no-schema", action="store_true",
                    help="compare with no definition (every record is new): another body's run, or a camera's with "
                         "no definition yet")
    ap.add_argument("--alone", action="store_true",
                    help=f"the run's own proofs only, into report_alone.json (report.json, which schema_update reads, "
                         f"stays as it is); by default the main run ({MAIN_RUN}) is reported with the camera's other "
                         f"proof runs (those marked {runs.PROOF_RUN}; proof_runs)")
    a = ap.parse_args()
    run = Path(a.run)
    if not (run / "proofs.jsonl").exists():        # never an empty report over the one before
        sys.exit(f"{run}: no proofs.jsonl (kit/prove_run.py writes it); no report made, report.json and report.md "
                 "left as they are")
    _BASE_DIRS[:] = [run / "dat", run]
    _RUNS_ROOT[:] = [run.parent]
    target = definitions.active()
    # the menu tree the report checks readings against is the mapper's own: one still in data/ is moved first
    datafiles.stop_if_left(target.stem, "the pass-2 report")
    if not target.exists() and not a.no_schema:
        sys.exit(f"no definition of {target.stem} yet ({target.relative_to(ROOT).as_posix()}): --no-schema reports "
                 "the run without comparing it with any definition, and kit/schema_update.py --write starts it")
    doc = definitions.load(target) if target.exists() else {"settings": []}
    parts = proof_runs(run, a.alone)
    for part in parts:
        why = models.refused(part, doc["model"], doc["layouts"][0]["firmware"],
                             f"editor/definitions/{target.name}") if target.exists() else ""
        if why and not a.no_schema:
            sys.exit(f"{why}. --no-schema reports the run without comparing it with any definition.")
    if len(parts) > 1:
        print(f"proofs read from {len(parts)} runs: {', '.join(p.name for p in parts)}", flush=True)
    schema = {} if a.no_schema else {s["key"]: s for s in doc["settings"]}
    try:
        cam = models.of_run(run)
    except ValueError as e:
        sys.exit(str(e))
    if not cam or cam[0] != models.A1II:
        DISP_MODES.clear()                     # the ILCE-1M2's own record ids (TODO decisions 19, 20)
        WRITTEN_BY.clear()
    report, counts = [], collections.Counter()
    proofs, skip, blocked, failed, reread = report_proofs(run, a.alone)
    cut = sorted({row_name(proofs[i]) for i in skip})
    if cut:
        print(f"left out: {len(skip)} proofs of {len(cut)} rows, from attempts that did not finish", flush=True)
    ROW_NAMES.update(norm(re.split(r" \[", p)[0]) for r in proofs for p in r.get("path") or [])
    MENU_NAMES.update(menu_names(definitions.menu_tree_file(target.stem) if target.exists() else None))
    hand = hand_rules(bool(cam) and cam[0] == models.A1II)
    readouts = frozenset(k for k, x in schema.items() if "view only" in (x.get("note") or "").lower())
    stood = stood_out(run, proofs, skip, schema, hand, readouts)
    if stood:
        gone = {row_name(proofs[i]) for i in stood}
        print(f"left out: {len(stood)} proofs of {len(gone)} rows made where the camera stood, beside lines that name "
              f"the state of a row they say nothing of and prove the same (stood_out): {', '.join(sorted(gone))}",
              flush=True)
    skip = skip | stood
    rows = rows_of(run, proofs, skip)
    carried, not_credited, kept_over, owners = credit_inputs(proofs, skip, rows, hand)
    lines = grid_lines([r for i, r in enumerate(proofs) if i not in skip])
    name_disputes, twins, samples = [], [], 0
    for name, opts in rows.items():
        recs, inferred, sources, disputes, held_back = row_values(rows, name, opts, schema, owners, not_credited,
                                                                  kept_over, readouts)
        notices = [o["notice"]["text"] for o in opts.values() if o.get("notice")]
        # the kinds of proof the row holds (list, axis, wbgrid...): the writer takes a grid's records as sampled scales
        from_start = sampled_from_start(opts)
        samples += from_start
        entry = {"row": name, "options": len(opts), "kinds": sorted({o["kind"] for o in opts.values()}), "records": {},
                 "notices": notices}
        if name in UNWALKED_CELLS:
            entry["cell_name"] = f"its own reading, with its place: {UNWALKED_CELLS[name]}"
        screens = screen_records(opts, kept_over)
        for c in carried:
            if c["row"] == name and c["key"] in screens:
                c["own_screen"] = True          # a copy of a function's own screen's record: no question of the key's
        kept = [{k: v for k, v in c.items() if k != "row"} for c in carried if c["row"] == name
                and not c.get("own_screen")]
        if kept:
            entry["carried_over"] = kept
        kinds = {o["kind"] for o in opts.values()}
        shared = two_labels_one_value(opts, recs)
        label_of = picker_names(opts)
        twins += [(name, lab) for lab in label_of.values() if re.search(r" \(\d+\)$", lab)]
        fallback = "carousel" if "axis" in kinds else "box" if "checklist" in kinds else \
            "grid readout" if "wbgrid" in kinds else None
        for key, vals in sorted(recs.items()):
            s = schema.get(key)
            mixed = not_one_to_one(proofs, name, key, vals, kinds, not_credited, label_of)
            if key in shared:
                mixed.append({"value": None, "camera": ", ".join(shared[key]), "schema": None, "kind": "not one to one",
                              "why": "two options of a one-record list wrote one value"})
            if mixed:
                verdict, notes = "conflict", mixed
            elif s is None:
                verdict, notes = "new", []
            elif "view only" in (s.get("note") or "").lower():
                verdict, notes = "readout", []         # a live value (ISO in use), not a setting
            elif any(o["kind"] == "checklist" for o in opts.values()) and \
                    any(lab.endswith((": ticked", ": unticked")) for lab in vals):
                verdict, notes = judge_ticks(vals, {v: lab for v, lab in s.get("values") or []})
            elif s.get("range") and (any(o["kind"] == "fields" for o in opts.values()) or
                                     all(num(lab) is not None for lab in vals)):
                # a number: its listed values are only samples; every stored value must be in range
                lo, hi = s["range"]
                out_of = [v for v in vals.values() if not lo <= v <= hi]
                verdict = "agrees" if not out_of else "conflict"
                notes = [{"value": v, "camera": None, "schema": f"range {lo}..{hi}", "kind": "conflict"} for v in out_of]
            elif any(o.get("opens") == "picker" for o in opts.values()):
                verdict, notes = judge_functions(vals, {v: lab for v, lab in s.get("values") or []})
            else:
                verdict, notes = judge(vals, {v: lab for v, lab in s.get("values") or []})
            entry["records"][key] = {"verdict": verdict, "schema_name": s["name"] if s else None,
                                     "proved": {lab: v for lab, v in vals.items()}, "notes": notes,
                                     # the line rule over every point read, a start line's too: a scale lists none
                                     "linear": scale_verdict(opts, kinds, key, {**held_back.get(key, {}), **vals}, s,
                                                             lines),
                                     "schema": {str(v): lab for v, lab in (s.get("values") or [])} if s else None}
            if key in inferred:
                # the labels taken from "nothing changed" (values_of), for a person reading this report (it stays in
                # the camera's runs/): kit/schema_update.py writes nothing of them, as one is the row's start
                entry["records"][key]["inferred"] = inferred[key]
            if from_start:
                entry["records"][key]["sampled_from_start"] = True     # a count in the definition, never these values
                # how many proofs: the lines that chose an option for its own sake, never a put-back ("planned": false)
                entry["records"][key]["sample_proofs"] = sum(1 for o in opts.values() if o.get("planned") is not False)
            if held_back.get(key):
                # what a start line would have credited (start_lines), for a person reading this report: the writer
                # keeps none of these values from an older definition unless a line proves it
                entry["records"][key]["start_only"] = {str(lab): v for lab, v in held_back[key].items()}
            came = record_runs(opts, vals, label_of, run.name, run.parent)
            if set(came) != {run.name}:
                entry["records"][key]["runs"] = came     # proofs of other runs, each its latest day (latest_run)
            allowed = record_allowances(opts, vals, label_of)
            if allowed:
                entry["records"][key]["allowances"] = allowed    # the owner's word for a never-open row (the note's evidence)
            # which readers back each name (name_of), a value taken from "nothing changed" as any other: a mark of its
            # own would tell the definition which value the record held when the row began (docs/decisions/0016)
            entry["records"][key]["names"] = {str(lab): (sources.get(key) or {}).get(lab, fallback) for lab in vals}
            argued = [{"row": name, "key": key, "value": v, **disputes[(key, lab)]}
                      for lab, v in vals.items() if (key, lab) in disputes]
            if argued:
                entry["records"][key]["name_disputes"] = [{k: d[k] for k in d if k not in ("row", "key")}
                                                          for d in argued]
                name_disputes += argued
        report.append(entry)
    seen = {}                                       # a record proved from several rows counts once
    for e in report:
        for k, r in e["records"].items():
            seen[k] = r["verdict"]
    counts = collections.Counter(seen.values())
    # whole, or the one before stays; the main run reported alone never stands in for its whole report
    out = "report_alone" if a.alone and run.name == MAIN_RUN else "report"
    write_json(run / f"{out}.json", report, indent=1, ensure_ascii=False)
    print(f"{len(report)} rows proved, {sum(e['options'] for e in report)} options; "
          f"{len(seen)} records: {dict(counts)}; "
          f"{sum(len(e['records']) > 1 for e in report)} rows write several records, "
          f"{sum(not e['records'] for e in report)} rows changed nothing")
    named = collections.Counter(src for e in report for r in e["records"].values() for src in r["names"].values())
    print(f"names: {dict(named)}; {len(name_disputes)} name disputes; {len(carried)} values carried over in "
          f"{len({c['row'] for c in carried})} rows ({sum(c['hand_rule'] for c in carried)} under a hand rule); "
          f"{len(twins)} picker twins; {reread} proofs read again (readings.jsonl); {samples} table rows sampled from the "
          "option the camera held (written as counts)")
    if not a.alone:
        lives, held = registration_mirrors(run), mirrored_values(run)
        if lives or held:
            print(f"registration mirrors: {len(lives)} live records whose memory copy a registration took, "
                  f"{sum(len(v['values']) for v in held.values())} values registered into {len(held)} memory records "
                  f"({', '.join(sorted({x['run'] for x in [*lives.values(), *held.values()]}))})")
    write_md(run, report, name_disputes, carried, twins, out, UNWALKED_CELLS)
    if name_disputes:
        print(f"\nname disputes ({len(name_disputes)}; the map's label stands, report.md lists them all):")
        for d in name_disputes[:40]:
            print(f"  {d['key']} {d['row'][:40]:40s} {d['value']!r:>6}: label {d['label']!r} shown {d['shown']!r} "
                  f"vision {d['vlm']!r}  {d['frame']}")
    if carried:
        print(f"\ncarried over ({len(carried)}; kept from the option before, not credited to the label):")
        for c in carried[:40]:
            print(f"  {c['key']} {c['row'][:50]:50s} {c['label']!r} kept {c['value']!r}"
                  + ("  [hand rule]" if c["hand_rule"] else "  [a function's own screen]" if c.get("own_screen") else ""))
    shown = set()
    for verdict in ("conflict", "missing", "new", "wording"):          # "readout": live values, not listed
        lines = []
        for e in report:
            for k, r in e["records"].items():
                if r["verdict"] != verdict or k in shown:
                    continue
                shown.add(k)
                lines.append(f"  {k} {e['row']}  (schema: {r['schema_name']!r})")
                for n in r["notes"]:
                    # a "not one to one" note is about a label, not one value (value None): listed with no number
                    v = "" if n["value"] is None else n["value"]
                    lines.append(f"      {v!s:>3}: schema {n['schema']!r:28s} camera {n['camera']!r}  [{n['kind']}]")
                if verdict == "new":
                    lines.append(f"      {r['proved']}")
        if lines:
            print(f"\n{verdict} ({counts[verdict]}):")
            print("\n".join(lines))
    for e in report:
        if not e["records"]:
            print(f"\nchanged nothing: {e['row']} ({e['options']} options)")
    mixed = [(e["row"], k, n) for e in report for k, r in e["records"].items() for n in r["notes"]
             if n["kind"] == "not one to one"]
    if mixed:
        print(f"\nnot one to one ({len(mixed)}; kit/schema_update.py leaves these records out until they are proved "
              "again):")
        for row, k, n in mixed[:40]:
            print(f"  {k} {row[:50]}: {n['camera']!r} {n['why']}")
    for row in cut[:40]:
        print(f"\nan attempt that did not finish (its proofs left out): {row}")
    if UNWALKED_CELLS:
        print(f"\ntable cells named by their own reading ({len(UNWALKED_CELLS)}; no walked cell at their place, so each "
              "keeps its own name with its place, never merged with another; the name may hold a value the camera "
              "held: walk the table again, kit/table_walk.py --rows <row>, and report again):")
        for row, why in sorted(UNWALKED_CELLS.items()):
            print(f"  {row[:70]:70s} {why}")
    for P, n, bad in grid_independence(run):
        print(f"\nWB grid {P}: {n} corner/inside points; " + ("each axis independent and linear" if not bad
              else f"{len(bad)} records off the axis lines: {bad[:4]}"))
    disagree = []
    for r in proofs:
        v = r.get("vlm")
        if v and r.get("kind") in ("list", "dialog", "sidelist", "axis", "table"):
            want = re.sub(r"[\s.:()]+", "", str(r.get("label", "")).lower())
            got = re.sub(r"[\s.:()]+", "", str(v).lower())
            if want and got and want not in got and got not in want:
                disagree.append((" > ".join(r["path"]), r.get("label"), v, r.get("chosen_frame")))
    if disagree:
        print(f"\nvLLM read something else on {len(disagree)} proofs (check the frames):")
        for row, lab, v, fr in disagree[:40]:
            print(f"  {row[:50]:50s} proved {lab!r:28s} vLLM {v!r:28s} {fr}")
    for name, opts in rows.items():
        for o in opts.values():
            if o.get("applied") is False and o["kind"] == "fields":
                print(f"\nrefused: {name} = {o['value']!r}; the camera kept {o['kept']!r} (a limit)")
            elif o.get("applied") is False:
                why = re.sub(r"\s+", " ", (o.get("notice") or {}).get("text") or "")
                print(f"\nrefused: {name} = {o['label']!r}: {why[:120]!r}")
    for e in report:
        for k, r in e["records"].items():
            if r["linear"] is not None:
                # a listed scale's or a grid's samples by count only: one of them is the row's start (decision 16)
                said = sorted(r['proved'].items(), key=lambda kv: num(kv[0]) or 0) \
                    if set(e.get("kinds", ())) & {"sidelist", "fields"} else f"{len(r['proved'])} samples"
                print(f"\nsampled: {e['row']} {k}: {'linear, the values between are inferred' if r['linear'] else 'NOT linear: prove every value'}"
                      f"  {said}")
    picker_rows = {name for name, opts in rows.items() if any(o.get("opens") == "picker" for o in opts.values())}
    clashes = code_clashes(report, picker_rows)
    if picker_rows:
        print(f"\npicker slots: {len(picker_rows)}; " + ("every function wrote one code in every slot" if not clashes
              else f"{len(clashes)} functions wrote different codes in different slots (prove those slots in full):"))
        for lab, codes in clashes[:40]:
            print(f"  {lab[:30]:30s} " + "; ".join(f"{v}: {', '.join(rows)[:80]}" for v, rows in codes.items()))
    if blocked:
        print(f"\nrows the camera would not open ({len(blocked)}; pass 3 switches the blocker):")
        for row, why in sorted(blocked.items()):
            print(f"  {row[:60]:60s} blocked by {why!r}")
    if failed:
        print(f"\nrows that failed and have no proof since ({len(failed)}; --retry-failed):")
        for row, why in sorted(failed.items()):
            print(f"  {row[:60]:60s} {why[:110]}")


def attach_readings(run: Path, proofs: list, prefix: str = "") -> int:
    """A proof with no vision reading of its own takes kit/tools/reread_proofs.py's of its chosen frame
    (<run>/readings.jsonl, the last line per frame; prefix: the run in front of its frames' names, qualified). Returns
    how many took one."""
    f = run / "readings.jsonl"
    if not f.exists():
        return 0
    got = {prefix + r["frame"]: r["reading"] for r in jsonl.read(f) if r.get("reading")}
    n = 0
    for p in proofs:
        if not p.get("vlm") and p.get("chosen_frame") in got:
            p["vlm"], p["vlm_reread"] = got[p["chosen_frame"]], True
            n += 1
    return n


def hand_rules(a1ii: bool) -> set:
    """The records the ILCE-1M2's hand rules already name (WRITTEN_BY, DISP_MODES here, KEEP_LABELS in its hand tables,
    data/ILCE-1M2_fw4.00/hand_tables_ILCE-1M2_fw4.00.json): a value carried over in one of them is reported and left to
    that rule. None on another body (TODO decisions 19, 20)."""
    if not a1ii:
        return set()
    try:
        from writer import hand_tables
        KEEP_LABELS = hand_tables.load(paths.A1II, evidence=False).KEEP_LABELS
    except Exception as e:                      # noqa: BLE001 - reported, and the verdict then covers those too
        print(f"(the hand tables' KEEP_LABELS not read: {e})", flush=True)
        KEEP_LABELS = set()
    return {k.split("[")[0] for k in set(WRITTEN_BY) | DISP_MODES | set(KEEP_LABELS)}


def write_md(run: Path, report: list, disputes: list, carried: list, twins: list, name: str = "report",
             unwalked: dict | None = None):
    """<run>/report.md (<name>.md): the names the readers did not agree on, the values carried over, the picker
    twins and the table cells named by their own reading (unwalked: UNWALKED_CELLS), in full. The proved values only
    (codes and the camera's option names), never a start value; it stays in runs/."""
    lines = ["# Pass-2 report: names", "",
             f"{len(report)} rows proved. Each value's name and which readers back it are in {name}.json (`names`).", "",
             f"## Name disputes ({len(disputes)})", "",
             "The map's label stands; the bar's OCR (shown) or the vision model disagreed with it. Check the frame.", "",
             "| row | key | value | label | shown | vision | frame |", "|---|---|---|---|---|---|---|"]
    cell = lambda t: str(t if t is not None else "").replace("|", "\\|")
    lines += [f"| {cell(d['row'])} | {d['key']} | {cell(d['value'])} | {cell(d['label'])} | {cell(d['shown'])} | "
              f"{cell(d['vlm'])} | {cell(d['frame'])} |" for d in disputes]
    lines += ["", f"## Carried over ({len(carried)} values, {len({c['row'] for c in carried})} rows)", "",
              "A record kept what the option before wrote while other records moved: not credited to the label "
              "(under a hand rule: left to it).", "",
              "| row | key | label | kept value | hand rule |", "|---|---|---|---|---|"]
    lines += [f"| {cell(c['row'])} | {c['key']} | {cell(c['label'])} | {cell(c['value'])} | "
              f"{'yes' if c['hand_rule'] else ''} |" for c in carried]
    lines += ["", f"## Picker twins ({len(twins)})", "", "One function listed twice, told apart by its place.", ""]
    lines += [f"- {cell(row)}: {cell(lab)}" for row, lab in twins]
    if unwalked:
        lines += ["", f"## Table cells named by their own reading ({len(unwalked)})", "",
                  "No cell of the walked table (kit2_tables/tables.json) sits at the proof's place: each keeps its own "
                  "reading with its place, never merged with another cell. The name may hold a value the camera held; "
                  "walk the table again (kit/table_walk.py --rows) and report again.", ""]
        lines += [f"- {cell(row)}: {cell(why)}" for row, why in sorted(unwalked.items())]
    (run / f"{name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def code_clashes(report: list, picker_rows: set) -> list:
    """The function picker's codes are one list for the whole camera, which is what lets
    prove_run.py --picker-sample prove one slot of each list in full and only three functions on the
    others (the project log). A function that wrote different codes in two slots disproves that for
    them: [(label, {code: [rows]})], each such slot to be proved in full (--rows, no --picker-sample)."""
    # one code table per screen (proved 2026-10-29: Pre-Capture is 2081 on the Fn Menu, 2110 on a
    # Custom Key; the stills and movie halves of a screen share theirs): compared within a screen only.
    # Each record's own reading, so twins told apart by an icon (two "Fixed Speed STBY") are not one
    seen = collections.defaultdict(lambda: collections.defaultdict(set))
    for e in report:
        if e["row"] in picker_rows:
            screen_name = e["row"].split(" / ")[0]
            for r in e["records"].values():
                for lab, v in r["proved"].items():
                    seen[(screen_name, norm(lab))][v].add(e["row"])
    return [(f"{scr}: {lab}", {v: sorted(rows) for v, rows in codes.items()}) for (scr, lab), codes in sorted(seen.items())
            if len(codes) > 1]


def failing_frames(run: Path) -> dict:
    """{fail_key: the frames of its failures, in order} for the rows still failing, and for every carousel axis row
    whether it still fails or not (never the blocked ones): each failure cut an attempt short (unfinished). An axis
    proof carries no attempt tag, so a later retry that passes (Custom 3 proved alone after session A's two cut
    Focus Area / Custom 1 attempts, which the camera notes call for) would otherwise bring the cut attempts back, and
    with them the Custom 2 visits' values on the Spot size memories (review 4, 2026-11-09). Other rows' failures before
    a later proof stay out: their attempts are tagged, or their row finished since."""
    path = run / "failures.jsonl"
    if not path.exists():
        return {}
    _, failed = still_failing(run)
    out = collections.defaultdict(set)
    for r in jsonl.read(path):
        if not r.get("blocked") and (fail_key(r) in failed or r.get("kind") == "axis"):
            out[fail_key(r)].add(frame_no(r.get("frame")))
    return {k: sorted(v) for k, v in out.items()}


def still_failing(run: Path) -> tuple:
    """({row: blocker} the camera refused to open, {row: last reason} that failed otherwise), for
    rows with no proof written after their last failure (failures and proofs share the frame numbers)."""
    path = run / "failures.jsonl"
    if not path.exists():
        return {}, {}

    key = fail_key
    last_proof = collections.defaultdict(int)
    for r in jsonl.read(run / "proofs.jsonl"):
        last_proof[key(r)] = max(last_proof[key(r)], frame_no(r.get("chosen_frame")), frame_no(r.get("dat")))
        last_proof[" > ".join(r["path"])] = max(last_proof[" > ".join(r["path"])], last_proof[key(r)])
        if r.get("part_of"):                  # a row proved by its parts, each a row of its own (Playback Filter
            last_proof[r["part_of"]] = max(last_proof[r["part_of"]], last_proof[key(r)])   # Condition, 2026-11-07)
    blocked, failed = {}, {}
    for r in jsonl.read(path):
        k = key(r)
        if last_proof.get(k, 0) > frame_no(r.get("frame")):
            blocked.pop(k, None)
            failed.pop(k, None)
            continue
        if r.get("blocked"):
            blocked[k] = r["blocked"]
            failed.pop(k, None)
        else:
            failed[k] = r["why"]
    return blocked, failed


if __name__ == "__main__":
    main()
