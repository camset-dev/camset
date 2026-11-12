"""Matching an option's reading to its label: one set of rules for every prover (2026-10-31).

OCR slips that must still match: case and spacing, a dot dropped ("Sec" / "Sec."), "l" / "1" / "|"
and "O" / "0", Cyrillic look-alikes ("С.Temp", "120р"), the radio ring read before or after the
label ("o Standard", "4 O"), an odd letter in a long word ("Contlnuous").
Labels that must never match, each once taken for the other on the a1 II:
  "1/4000" / "1/400", "1/10000" / "1/1000"   digits are compared exactly
  "F1.1" / "F11"                             a decimal point between digits is kept
  "Cont. Shooting: Hi+" / "...: Lo"          a close reading must end on the same word
  "Lo" / "10"                                a word is not a number, whatever its look-alikes
  "Lo (E-Shutter)" / "Hi(E-Shutter)"         a short word (3 letters or fewer) is compared exactly

Row labels (`prove_run.closest_row`) and picker function names (`prove_run.closest_function`) keep
their own matchers: they pick the clearly closest of many readings, with a margin over the next.
"""
import collections
import difflib
import re

CYRILLIC = str.maketrans("аеорсухкмтвн", "aeopcyxkmtbh")    # lower case of OCR's look-alikes ("С.Temp", "120р")
# Cyrillic letters the screen readers return for Latin ones ("С.Temp./Filter"), both cases, as the camera's labels are
# mended in camkit.placement and camkit.option_tree (camkit.safety folds these and more)
LOOKALIKES = str.maketrans("СсАаЕеОоРрТтНМВКХху", "CcAaEeOoPpTtHMBKXxy")


def key(t) -> str:
    """Compared without case, spaces, dots or OCR look-alikes (a leading number is kept); the seconds mark after a
    shutter time is one character however it is drawn (2", 2″, 2”, or two apostrophes 2'': the readers differ,
    2026-11-07)."""
    t = str(t or "").lower().translate(CYRILLIC).replace("″", '"').replace("”", '"').replace("“", '"').replace("''", '"')
    return re.sub(r"[\s.]+", "", t.translate(str.maketrans("l1|0", "iiio")))


def offers_ok(text) -> bool:
    """A screen's footer offers OK: the word OK in any case, its Cyrillic look-alikes folded (CYRILLIC: OCR reads "ОK"
    and "Ок", 2026-11-10) and a 0 taken for the O, never inside a word or a number ("Look", "10K")."""
    t = str(text or "").lower().translate(CYRILLIC).replace("0", "o")
    return re.search(r"(?<![a-z0-9])ok(?![a-z0-9])", t) is not None


def clean(t) -> str:
    """An option's reading without its radio mark: a grey dot before most options, a ring before or
    after the selected one, which OCR reads as "o", "O" or a "0" glued to the label."""
    t = re.sub(r"^[•·◦●○]\s*", "", str(t or "").strip())
    t = re.sub(r"^[oO0]\s+(?=\S)", "", t)
    t = re.sub(r"^[oO](?=[\d+\-±‡])|^0(?=\d)", "", t)
    t = re.sub(r"(?<=\S)\s+[oO]$", "", t)
    return t.strip()


def norm(label) -> str:
    """The option's key: the ± before a zero reads as "‡", "I" or "+" too, and a decimal point
    between digits stays ("F1.1" against "F11")."""
    t = re.sub(r"^[‡±I|]\s*(?=\d)", "", clean(label))
    t = re.sub(r"^1(?=0\.0+$)", "", t)                  # "10.0": the ± read as a one
    t = re.sub(r"^[+-]\s*(?=0(?:\.0+)?$)", "", t)
    return key(re.sub(r"(?<=\d)\.(?=\d)", "p", t))


def _numeric(t) -> bool:
    return bool(re.fullmatch(r"[\d\s.,/:+\-±\"']+", clean(t))) and bool(re.search(r"\d", t))


def _wordy(t) -> bool:
    return not re.search(r"\d", clean(t))


def _words(t) -> list:
    """Words as key() spells them, split at the punctuation key() keeps ("Lo (E-Shutter)": lo, e, shutter)."""
    return re.findall(r"[^\W_]+\+?|\+", key(clean(t)))


def same(a, b) -> bool:
    if norm(a) == norm(b):
        # "Lo" and "10" share a key: a number never matches a word
        return not ((_numeric(a) and _wordy(b)) or (_numeric(b) and _wordy(a)))
    if re.search(r"\d", f"{a}{b}") or difflib.SequenceMatcher(None, norm(a), norm(b)).ratio() < 0.85:
        return False
    wa, wb = _words(a), _words(b)
    if len(wa) == len(wb) and any(x != y and min(len(x), len(y)) <= 3 for x, y in zip(wa, wb, strict=True)):
        return False
    ta, tb = (norm(re.split(r"[\s:]+", clean(t).strip())[-1]) for t in (a, b))
    return ta == tb or min(len(ta), len(tb)) >= 5 and difflib.SequenceMatcher(None, ta, tb).ratio() >= 0.8


def index_of(options: list, reading) -> int | None:
    """The one option the reading names: exactly, else the only one it matches."""
    hits = [i for i, o in enumerate(options) if norm(o) == norm(reading) and same(o, reading)]
    if not hits:
        hits = [i for i, o in enumerate(options) if same(o, reading)]
    return hits[0] if len(hits) == 1 else None


def table_row_label(labels) -> str:
    """A setting table's row label as the cells of the row read it (kit/table_walk.py reads it for each cell from the
    screen's left edge to the cell, so a cell further right reads the values of the cells before it glued on: "File
    Format RAW" on Slot 2's cell, "Rear Dial L -- --" on My Dial 3's), an icon read as a letter or a mark before it
    ("dFile Format", "•File Format", "mFront dial"): the longest stretch every reading shares, then without a mark or
    a lone letter glued before it and without "--" after it. A row read once keeps that reading, so cleaned. The value
    a cell held is the camera's own setting (docs/decisions/0016), never part of a row's name."""
    texts = [str(t).strip() for t in dict.fromkeys(labels) if str(t or "").strip()]
    if not texts:
        return ""
    common = texts[0]
    for t in texts[1:]:
        m = difflib.SequenceMatcher(None, common, t, autojunk=False).find_longest_match(0, len(common), 0, len(t))
        common = common[m.a:m.a + m.size]
    shortest = min(texts, key=len)
    if len(re.findall(r"[^\W\d_]", common)) < 3 or 2 * len(common.strip()) < len(shortest.strip()):
        common = shortest                     # readings too far apart to share a name: the shortest, cleaned
    common = re.sub(r"(?:\s+-{2,})+\s*$", "", common.strip())
    common = re.sub(r"^[^\w(]+", "", common)
    common = re.sub(r"^[a-z](?=[A-Z][a-z])", "", common)
    return common.strip()


def table_cells(cells: list) -> dict:
    """{index into cells: its row label as the row reads it (table_row_label)}: cells is [(the row, the label read on
    that cell)], the row any value one row's cells share (their height on the screen, with the table's name)."""
    rows = collections.defaultdict(list)
    for i, (y, label) in enumerate(cells):
        rows[y].append((i, label))
    return {i: table_row_label([lab for _, lab in got]) for got in rows.values() for i, _ in got}


def walked_cell_names(t: dict) -> list:
    """The name of each cell of one screen of kit/table_walk.py's tables.json (t: that screen's entry), in the order of
    t["cells"], as kit/proving/tables.py's table_jobs names its jobs: "<row label> / <column label>", a table's row as
    all that row's cells read it (table_cells), a Fn Menu's by its section; a name that is empty or that two cells of
    the screen share (unread or repeated headers) takes the cell's place after it ("... @x,y")."""
    cells = t.get("cells") or []
    rows = table_cells([(c["pos"][1], c["row_label"]) for c in cells]) if t.get("screen") == "table" \
        else {i: c["row_label"] for i, c in enumerate(cells)}
    names = [f"{rows[i]} / {c['col_label']}".strip(" /") for i, c in enumerate(cells)]
    count = collections.Counter(names)
    return [n if n and count[n] == 1 else f"{n} @{c['pos'][0]},{c['pos'][1]}".strip() for n, c in zip(names, cells, strict=True)]


def cell_options(proofs: list, tables: dict | None) -> tuple:
    """(proof lines with each setting table cell named as the walked table names it now, {each name a cell kept by its
    own reading: why}). A line written before 2026-11-11 names its cell by the reading of that cell alone ("<row
    label> / <column label>", the row label read from the screen's left edge to the cell, the values of the cells
    before it glued on: values the camera held, decision 16). tables is kit/table_walk.py's tables.json (None when
    there is none): the line takes the name of the walked cell (walked_cell_names) of its table (its path and "nth")
    whose place is the line's own "cell" [x, y], the place the guard, so two cells whose readings clean to one name are
    never one, nor is a cell another walk put elsewhere. A line no walked cell matches (no table file, or none at its
    place) keeps its own reading, cleaned (table_row_label), with its place after it ("... @x,y"): a name of its own,
    never merged with another cell's, and returned with why, for the report to say (pass2_report). A line of another
    kind, a Fn Menu tile, a key, or a cell named by its place ("... @x,y") stays as it was."""
    def cell(r):
        return r.get("kind") == "table" and r.get("screen", "table") == "table" and isinstance(r.get("option"), str) \
            and " @" not in r["option"] and isinstance(r.get("cell"), list) and len(r["cell"]) == 2

    walked = {}
    for t in (tables or {}).values():
        if t.get("screen") == "table":
            for c, name in zip(t.get("cells") or [], walked_cell_names(t), strict=True):
                walked[(tuple(t.get("path") or ()), t.get("nth", 0), tuple(c["pos"]))] = name
    out, unwalked = list(proofs), {}
    for i, r in enumerate(proofs):
        if not cell(r):
            continue
        x, y = r["cell"]
        name = walked.get((tuple(r.get("path") or ()), r.get("nth", 0), (x, y)))
        if name is None:
            row, sep, col = r["option"].rpartition(" / ")
            row, col = (row, col) if sep else (r["option"], "")
            name = f"{f'{table_row_label([row])} / {col}'.strip(' /')} @{x},{y}".strip()
            unwalked[name] = "no table file (kit/table_walk.py's tables.json)" if not tables else \
                f"no cell of the walked table {' > '.join(r.get('path') or ())} at {x},{y}"
        if name != r["option"]:
            out[i] = {**r, "option": name}
    return out, unwalked
