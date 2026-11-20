"""What a setting's list holds, by what the camera's menus offer. A picker's list walked whole (walked_lists): the
values a first kit listed that the walk shows the picker never offers are taken out, so a setting lists exactly the
codes its picker's walks wrote. Values the camera's menus never offer (not_offered): each mark a table names, written
only when the evidence it cites holds, so a rerun after a new walk drops a mark the camera contradicts. And the values
they offer under one video system only (video_system_values), from the rows walked under each system, the downloads'
headers saying which, checked against the camera's own downloads at every write."""
import collections
import difflib
import functools
import json
import re
import sys
from pathlib import Path

from camkit import match, row_names
from pass2_report import alike, element_changes, row_name, strip_icon

# a report row's context, after its menu path and cell ("... / Still Upper / 1 [Movie mode]")
CONTEXT = re.compile(r" \[[^\]]*\]$")
# a setting key the sample is read by: a live record, whole or one element of it
LIVE_KEY = re.compile(r"global:0x([0-9a-f]{4})(?:\[(\d+)\])?")


def walk_matches(pattern: str, row: str) -> bool:
    """Whether a walk's pattern (the hand tables' NOT_OFFERED and PICKER_LISTS "walk") matches the report's row: as
    named, as the camera draws it, or as any older name the camera's ROW_NAMES gives it (camkit.row_names), so a pattern
    written before a row was renamed still finds it."""
    return any(re.search(pattern, name) for name in row_names.names(row))


class NotCut(Exception):
    """Why a picker's list is not cut to its walks, in words: the list stays as it is, and the run says why."""


def sample_values(path, keys) -> dict | None:
    """{key: the value the definition's sample (the scrubbed file the camera wrote right after Initialize) holds} for
    each of `keys` a live record of the sample holds (a whole record's value, or one element's); None when there is no
    sample (`path` None, or no such file)."""
    from camkit import camset
    if path is None or not Path(path).exists():
        return None
    return live_values(camset.read(path), keys)


def live_values(cs, keys) -> dict:
    """{key: the value a settings file (`cs`, camkit.camset's) holds in its live settings} for each of `keys` a live
    record of it holds: a whole record's value, or one element's."""
    out = {}
    for k in keys:
        m = LIVE_KEY.fullmatch(k)
        rec = cs.get(0, int(m[1], 16)) if m else None
        if rec is None:
            continue
        got = rec.values()
        if m[2] is None and rec.count == 1 and len(got) == 1:
            out[k] = got[0]
        elif m[2] is not None and int(m[2]) < len(got):
            out[k] = got[int(m[2])]
    return out


def walked_list(name: str, entry: dict, doc: dict, report: list, tables: dict, proofs: list | None,
                readings: dict | None = None, said: list | None = None) -> tuple:
    """(the codes the picker's walks wrote, the settings its list is theirs for) for one PICKER_LISTS entry, or NotCut
    saying why not. `entry`: the settings it covers ("keys", a pattern for their keys), the report's rows that walked
    the list whole ("walk", a pattern), the table walk's screen ("table", [screen, page or section or null]) and what
    shows the walks went round ("evidence", the hand evidence's); `proofs`: the proof lines the report counts;
    `readings`: the functions the camera has (picker_readings, read here when None; none refuses the entry, for then
    nothing shows a cell offers no other function); `said`, where given, gets a line saying how many functions outside
    the walked list the picker screens showed and which codes were taken as one name. Each condition refuses rather
    than guesses:
      - the hand evidence gives it ("evidence"), and some setting is covered;
      - every covered setting has a cell of its own on that screen (in that page or section where the entry names
        one): a report row that proves it and no other covered setting, for a row that writes another slot along with
        its own stands for no slot's list but its own; every such cell, and every walk's, went round to its start in
        the table walk (kit/table_walk.py's "wrapped") and lists the same functions in the same order as the first
        walk's, numbers alike (match.same_functions with numbers: "Hold 3" is never "Hold 4"; a list turned round to its
        saved function alike) but at an icon place (icon_places: a code the camera's readings on that screen give with
        differing numbers, an icon read as digits), where the numbers must be some the camera read for that code, and
        no label reading nearer a function the camera has outside the walked list than the walked one at its place
        (stands_for_other: the cell may offer another set of functions): the settings choose from one list;
      - every row the walk names proves one covered setting, and chose every place of the list (walk_problem: its
        proof lines chose each place of the walked cell, by index, the put-back counted only where it was planned, none
        past its end and each planning the label the table walk reads at its place) and none is a sample stepped from
        the held option ("sampled_from_start"); it names as many options and wrote as many distinct codes as the list
        has places, and all walks wrote the same codes, none empty;
      - every row that proves a covered setting was made in a state some walk names (its context, "[Movie mode]", or
        none): a list that may change with the camera's state is cut only on walks in each state it was proved in.
    Judged by code, never by name: two functions read alike stay two codes, and a code one row wrote for one slot of an
    array record stands for every slot the table walk shows with the same list."""
    covered = [s for s in doc["settings"] if re.search(entry["keys"], s["key"])]
    if not entry.get("evidence"):
        raise NotCut("the hand evidence says nothing of the walks (PICKER_LISTS in the hand evidence file), so nothing "
                     "shows they went round")
    if not covered:
        raise NotCut(f"no setting of the definition matches its keys, {entry['keys']!r}")
    screen, part = entry["table"]
    walked = walked_cells(tables, screen)
    if not walked:
        raise NotCut(f"the table walk has no screen {screen!r}")
    base = lambda row: CONTEXT.sub("", row)
    where = f"{screen!r}" + (f"'s {part!r}" if part else "")
    # a row on the entry's screen, in its page or section where it names one (a Fn menu's Still rows, not its Movie
    # rows, which may write a Still slot along with their own)
    on = lambda row: base(row) in walked and (part is None or walked[base(row)][1] == part
                                              or walked[base(row)][1].startswith(part + " "))
    keys = {s["key"] for s in covered}
    lists = {}                     # the report's row -> its walked cell
    for s in covered:
        own = [e["row"] for e in report if on(e["row"]) and s["key"] in e["records"] and not keys & set(e["records"]) - {s["key"]}]
        if not own:
            raise NotCut(f"no row of the report on {where} proves {s['key']} alone (its own cell), so nothing shows "
                         "which list its picker offers")
        lists.update({row: walked[base(row)][0] for row in own})
    walks = [e for e in report if walk_matches(entry["walk"], e["row"])]
    if not walks:
        raise NotCut(f"no row of the report matches its walk, {entry['walk']!r}")
    if proofs is None:
        raise NotCut("no proof lines to show that its walks chose every place")
    wrote = []
    for e in walks:
        mine = sorted(keys & set(e["records"]))
        if len(mine) != 1:
            raise NotCut(f"{e['row']} proves {'none' if not mine else len(mine)} of the settings it covers, so it "
                         "walks no one setting's list")
        if not on(e["row"]):
            raise NotCut(f"{e['row']} is no cell, key or tile of {where} in the table walk")
        lists[e["row"]] = item = walked[base(e["row"])][0]
        r, n = e["records"][mine[0]], len(item.get("options") or [])
        codes = frozenset(v for v in r["proved"].values() if isinstance(v, int) and not isinstance(v, bool))
        if r.get("sampled_from_start"):
            raise NotCut(f"{e['row']} chose a sample of its list, not every place")
        why = walk_problem(e["row"], item, proofs)
        if why:
            raise NotCut(f"{e['row']} {why}")
        if len(r["proved"]) != n or len(codes) != n:
            raise NotCut(f"{e['row']} names {len(r['proved'])} options and wrote {len(codes)} distinct codes, and its "
                         f"list has {n} places: not one code to each place")
        wrote.append(codes)
    if len(set(wrote)) != 1 or not wrote[0]:
        raise NotCut("the walks it names wrote different codes" if wrote[0] else "its walks wrote no code")
    states = {state(e["row"]) for e in walks}
    for e in report:
        for k in sorted(keys & set(e["records"])):
            if state(e["row"]) not in states:
                raise NotCut(f"{e['row']} proves {k} in a state no walk names ({state(e['row'])}): a list that may "
                             "change with the camera's state is walked in each state, every walk named, or marked "
                             "NOT_OFFERED instead")
    first = walks[0]["row"]
    ref = [o["label"] for o in lists[first].get("options") or []]
    fkey = sorted(keys & set(walks[0]["records"]))[0]
    on_screen = code_readings(screen, report, tables, proofs)
    free = icon_places(screen, first, fkey, report, tables, proofs, on_screen)
    codes = walk_codes(first, fkey, proofs, wrote[0], len(ref))
    readings = picker_readings(tables, report, proofs) if readings is None else readings
    if not readings:
        raise NotCut("the table walk's picker screens gave no function readings (no counted proof line wrote a code "
                     "on them), so nothing shows its cells offer no function outside the walked list")
    # each label's answer at a place, kept over the cells; the codes taken as one name; the icon places whose numbers
    # were excused as naming no other function (the cell's label and the walked one)
    memo, alike, excused = {}, set(), set()
    for row, item in lists.items():
        if item.get("opens") not in ("picker", "list") or not item.get("wrapped"):
            raise NotCut(f"{row}'s list on {screen!r} was not walked round to its start")
        why = differs([o["label"] for o in item.get("options") or []], ref, free, codes, wrote[0], readings, memo,
                      on_screen, alike, excused)
        if why:
            raise NotCut(f"{row}'s list on {screen!r} {why}")
    if said is not None:
        said.append(f"  vocabulary  {name}: {sum(1 for c in readings if c not in wrote[0])} functions the picker "
                    f"screens showed outside its walked list; codes taken as one name: "
                    + (", ".join(f"{c} and {c2}" for c, c2 in sorted(alike)) or "none"))
        said.append(f"  icon numbers  {name}: excused as naming no other function: "
                    + ("; ".join(f"{x!r} where the walked list reads {y!r}" for x, y in sorted(excused)) or "none"))
    return wrote[0], covered


def counted(p: dict) -> bool:
    """A proof line counts as a choice of its place: a place (index) it chose, applied, and planned (a put-back of the
    option the camera held counts only where it was planned)."""
    return isinstance(p.get("index"), int) and not isinstance(p.get("index"), bool) and p.get("applied") is not False \
        and p.get("planned") is not False


def aligned(p: dict, options: list) -> bool:
    """A proof line's place is the table walk's: its index inside the walked cell's list (`options`) and the label it
    planned to choose reading that place's label (the same, or match.nearness 0.8 or more). A line that does not was
    made on a list the table walk has read again since, turned or changed: its place names another function."""
    i, planned = p.get("index"), p.get("label")
    if not isinstance(i, int) or not 0 <= i < len(options) or not isinstance(planned, str):
        return False
    cell = options[i].get("label") or ""
    return planned == cell or match.nearness(planned, cell) >= 0.8


def walk_problem(row: str, item: dict, proofs: list) -> str | None:
    """Why a row's proof lines did not choose the whole list of its walked cell (`item`, the table walk's), in words,
    or None when they did: every place chosen by a counted line (counted), none past the list's end, and each planning
    the label the table walk reads at its place (aligned; else the table walk was read again since the walk). The words
    name no place, for a place counts from the option the camera held."""
    options = item.get("options") or []
    n = len(options)
    mine = [p for p in proofs or () if row_name(p) == row and counted(p)]
    if any(not 0 <= p["index"] < n for p in mine):
        return f"has a proof line past its list's {n} places: the table walk was read again since the walk"
    off = [p for p in mine if not aligned(p, options)]
    if off:
        return (f"has {len(off)} proof lines planning another label than the table walk's at their place ("
                f"{off[0].get('label')!r} where the walk reads {options[off[0]['index']].get('label')!r}): the table "
                "walk was read again since the walk")
    chose = {p["index"] for p in mine}
    if chose != set(range(n)):
        return f"chose {len(chose)} of its list's {n} places: not every place"
    return None


def line_code(p: dict, key: str) -> int | None:
    """The code a proof line wrote into `key` (a record, or one slot of an array record, "global:0x0445[3]"): the
    value it changed there, against the run's start (pass2_report.element_changes); None where it changed nothing
    there (it chose the option the camera held)."""
    for c in element_changes(p) if "changes" in p else ():
        if c["key"] == key and isinstance(c["after"], int) and not isinstance(c["after"], bool):
            return c["after"]
    return None


def code_readings(screen: str, report: list, tables: dict, proofs: list) -> dict:
    """{code: the readings the camera's screens gave its function} on one screen of the table walk: from every row on
    it that proves one record (a cell of its own), each counted proof line that wrote a code there (line_code): the
    walked cell's label at the line's place, the label it planned to choose and the menu's own reading when it chose
    (its "shown"). All three, for a code one source reads alike every time another reads otherwise. A line whose
    planned label does not read the cell's label at its place (aligned: the table walk was read again since) gives
    none, for its place may name another function."""
    cells = walked_cells(tables, screen)
    own = {e["row"]: next(iter(e["records"])) for e in report
           if len(e["records"]) == 1 and CONTEXT.sub("", e["row"]) in cells}
    out = {}
    for p in proofs or ():
        row = row_name(p)
        if row not in own or not counted(p):
            continue
        options = cells[CONTEXT.sub("", row)][0].get("options") or []
        code = line_code(p, own[row])
        if code is None or not aligned(p, options):
            continue
        said = [options[p["index"]].get("label"), p.get("label"), p.get("shown")]
        out.setdefault(code, set()).update(t for t in said if isinstance(t, str) and t.strip())
    return out


def icon_places(screen: str, row: str, key: str, report: list, tables: dict, proofs: list | None,
                readings: dict | None = None) -> frozenset:
    """The places of a walk (`row`, writing `key`, on `screen` of the table walk) where the camera draws an icon by its
    function's name that the reader gives as differing digits or letters ("8Var. Shutter", "S Var. Shutter"; the
    rating stars "(34)", "(24)"): each place one code was written at by the walk's counted lines (line_code) whose
    readings on that screen (code_readings, given as `readings` or read here) hold more than one set of numbers
    (match.label_numbers). A code read with one set of numbers everywhere is no icon place, so "Recall Custom hold 2"
    stays apart from "hold 3" until the reader misreads one of them somewhere on the screen; nor is a place no line of
    the walk wrote a code at (its start, the option the camera held), nor one it wrote two codes at; nor any with no
    proof lines."""
    if not proofs:
        return frozenset()
    readings = code_readings(screen, report, tables, proofs) if readings is None else readings
    varies = lambda code: len({match.label_numbers(t) for t in readings.get(code, ())}) > 1
    return frozenset(i for i, code in walk_codes(row, key, proofs).items() if varies(code))


def walk_codes(row: str, key: str, proofs: list | None, walked=frozenset(), places: int = 0) -> dict:
    """{place: the code a walk (`row`, writing `key`) wrote there}: each place's code by the walk's counted lines
    (line_code; a place they wrote two codes at is left out). Its start, where no line wrote a code (the option the
    camera held), is the one code of `walked` (the codes the walk proved) no other place holds, where exactly one of its
    `places` lacks a code; with no `walked` the start has none."""
    got = {}
    for p in proofs or ():
        if row_name(p) == row and counted(p):
            code = line_code(p, key)
            if code is not None:
                got.setdefault(p["index"], set()).add(code)
    out = {i: next(iter(codes)) for i, codes in got.items() if len(codes) == 1}
    missing, left = [i for i in range(places) if i not in out], set(walked) - set(out.values())
    if len(missing) == 1 and len(left) == 1:
        out[missing[0]] = left.pop()
    return out


def picker_readings(tables: dict, report: list, proofs: list | None) -> dict:
    """{code: its readings}: the functions the camera has, by what its screens showed for each code, joined over every
    picker screen of the table walk (a Fn menu, a Custom Key screen, a table with a picker cell such as My Dial
    Settings; code_readings on each). {} with no proof lines, or none that wrote a code on such a screen."""
    out = {}
    for name, t in (tables or {}).items() if proofs else ():
        if t.get("screen") in ("fnmenu", "keyset") or any(c.get("opens") == "picker" for c in t.get("cells") or []):
            for code, said in code_readings(name, report, tables, proofs).items():
                out.setdefault(code, set()).update(said)
    return out


# How near two readings of function names must come (difflib's ratio of match.function_name, as match.nearness has
# it), with the same numbers in them, for the check that a cell offers no function outside its walked list
# (stands_for_other) to take two codes for one name, which no label can tell apart. On the a1 II, Pre-Capture,
# Subject Recog in AF, SteadyShot, Protect, Clip Flag OK, NG and KEEP, and Fixed Speed STBY and REC each stand under
# two codes, their readings 0.96 to 1.0 alike; two distinct functions one short word apart in a short name read below
# it (Zoom Operation (T) and (W) 0.938), and one digit apart they hold other numbers (Recall Custom hold 1 and 2, 0.941;
# Recall Shooting Set. Memory 2 and 4, 0.958). A tolerance of the comparison, as same_functions' 0.8 is, not a fact of a
# camera: which codes share a name is read from the camera's own screens. A camera whose distinct functions read
# nearer than this with the same numbers only loses the check for those pairs, its codes still held by kept_codes and
# check_cut_downloads; if a mapping shows such a pair, raise it here, above the pair, and say so.
SAME_NAME = 0.95


@functools.cache
def _name(label: str) -> tuple:
    """(match.function_name of a reading, its length, its characters counted): what nearer's bounds read."""
    k = match.function_name(label)
    return k, len(k), collections.Counter(k)


def nearer(mine: tuple, other: tuple, own: float, quick: bool = True) -> bool:
    """Whether a reading (`mine`, _name's) is strictly nearer another (`other`) than `own`, by difflib's ratio, which
    real_quick_ratio (the lengths) and quick_ratio (the characters in common) bound from above: with `quick` either
    bound at or under `own` answers no before the ratio is worked out, the same answer as without, sooner."""
    (a, la, ca), (b, lb, cb) = mine, other
    if quick and la + lb and (2 * min(la, lb) / (la + lb) <= own or 2 * sum((ca & cb).values()) / (la + lb) <= own):
        return False
    return difflib.SequenceMatcher(None, a, b).ratio() > own


def same_name(c: int, c2: int, readings: dict, others: dict | None = None) -> bool:
    """Two codes no label tells apart: some reading of each (c's in `readings`, c2's in `others`, the same where not
    given) within SAME_NAME of a reading of the other, with the same numbers (match.label_numbers): "Recall Shooting
    Set. Memory 2" and "Memory 4" read 0.958 alike, yet the numbers tell them apart."""
    return any(difflib.SequenceMatcher(None, _name(x)[0], _name(y)[0]).ratio() >= SAME_NAME
               and match.label_numbers(x) == match.label_numbers(y)
               for x in readings.get(c, ()) for y in (readings if others is None else others).get(c2, ()))


def stands_for_other(a: list, b: list, r: int, codes: dict, walked, readings: dict, memo: dict | None = None,
                     quick: bool = True, own_readings: dict | None = None, alike: set | None = None) -> int | None:
    """The first place of a cell's list `a`, beside the walked list `b` at turn r (match.turns: a's place i beside b's
    place j = (i + r) % len(b)), whose label reads strictly nearer a function the camera has outside the walked list (a
    code of `readings`, picker_readings, not in `walked`) than the walked function there (its readings, by its code in
    `codes`, on the entry's own screen where `own_readings` gives them, code_readings, else in `readings`, and the
    walked label b[j]); a function whose readings come within SAME_NAME of the walked one's with the same numbers (the
    same name under another code) is passed over, for no label tells those apart, the pair added to `alike` where
    given. None when there is none: the cell offers the walked set of functions as far as its labels show. A swap of
    two functions both in the walked list passes, for the set of codes is the same (a picker never lists a function
    twice). `memo` keeps each label's answer at a place over one walked list's cells; `quick` the bounds that skip most
    ratios (nearer)."""
    n = len(b)
    own_readings = readings if own_readings is None else own_readings
    outside = [(c2, [_name(t) for t in sorted(rd)]) for c2, rd in readings.items() if c2 not in walked]
    for i, x in enumerate(a):
        j = (i + r) % n
        if memo is not None and (x, j) in memo:
            if memo[(x, j)]:
                return i
            continue
        c, mine = codes.get(j), _name(x)
        names = {_name(t)[0] for t in [*own_readings.get(c, ()), b[j]]}
        own = 1.0 if mine[0] in names else max(difflib.SequenceMatcher(None, mine[0], t).ratio() for t in names)
        other = False
        for c2, rd in outside if own < 1.0 else ():
            if any(nearer(mine, t, own, quick) for t in rd):
                if not same_name(c, c2, own_readings, readings):
                    other = True
                    break
                if alike is not None:
                    alike.add((c, c2))
        if memo is not None:
            memo[(x, j)] = other
        if other:
            return i
    return None


@functools.cache
def _bare(label: str) -> str:
    """A picker label's name without its icon or any digit (match.function_name of what is left; the digits go before
    key() would read a 1 or a 0 as a letter): "8Zebra Level" and "fZebra Level" read alike, so do the rating stars."""
    return match.function_name(re.sub(r"\d", "", match.ICON.sub("", str(label or ""))))


def numbers_matter(x: str, c: int | None, walked, readings: dict, own: dict | None = None) -> bool:
    """Whether a cell label's numbers, which the camera never read for the walked function at its icon place (code
    `c`), may name another function than it. They cannot when every function the camera showed (`readings`,
    picker_readings) whose name reads near the label's, digits aside (match.nearness's 0.8, on _bare), is in the
    walked list (`walked`), the walked one among them, and the reader cannot read that function's numbers apart at its
    place: it is the only one ("8Zebra Level" where the walked list reads "fZebra Level": no second function of that
    name exists), or the reader gave it a sibling's numbers (digits, not their absence), or its own readings on the
    entry's screen (`own`,
    code_readings; `readings` where not given) disagree among three or more sets of numbers (five stars read "(14)",
    "(2)", "(24)", "(34)"). Each is tied to the place's own function: siblings that each read with numbers of their own
    there ("Recall Custom hold 1", "2", "3", whatever another pair once shared), or a near name outside the walked list
    ("Recall Custom hold 4" shown on the Fn menu), and the numbers matter, for a number never read may be a function the
    camera never showed. Whichever function the camera showed under that name the cell holds there, its code is one the
    cut keeps; a function no screen showed, or one shown only under a reading too far from its name, is beyond it."""
    name = _bare(x)
    family = {c2 for c2, rd in readings.items()
              if any(difflib.SequenceMatcher(None, name, _bare(t)).ratio() >= 0.8 for t in rd)}
    if c not in family or family - set(walked):
        return True
    mine = {match.label_numbers(t) for t in (readings if own is None else own).get(c, ())} - {()}
    if family == {c} or len(mine) >= 3:
        return False
    return not any(mine & {match.label_numbers(t) for t in readings[k]} for k in family - {c})


def differs(a: list, b: list, free=frozenset(), codes: dict | None = None, walked=frozenset(),
            readings: dict | None = None, memo: dict | None = None, own_readings: dict | None = None,
            alike: set | None = None, excused: set | None = None) -> str | None:
    """Why a picker's list `a` (its labels as the table walk read them) is not the walked list `b`, in words naming the
    labels that differ, or None when it is: the same functions in the same order, numbers alike but at b's icon places
    `free` (match.turns), where a label's numbers must be some the camera read for that place's code (`own_readings`,
    the entry's screen's, else `readings`) or the walked label's own, unless they cannot name another function there
    (numbers_matter; each such place, the cell's label and the walked one, added to `excused` where given), and at some
    such turn no label reading nearer a function outside the walked list than the walked one there (stands_for_other,
    by the walk's `codes` place by place, its set `walked` and the camera's `readings`). With no readings (a camera
    whose table walk gave none) nothing shows the cell offers no other function, and it is refused."""
    found = list(match.turns(a, b, numbers=True, free=free))
    if not found:
        return "is not the walked one (other functions, numbers or order)"
    codes, n = codes or {}, len(b)
    own = (readings or {}) if own_readings is None else own_readings
    nums = lambda j: {match.label_numbers(t) for t in own.get(codes.get(j), ())} | {match.label_numbers(b[j])}
    # at a turn, the icon places whose label holds numbers the camera never read for the place's code, and whether
    # those numbers may name another function there (numbers_matter)
    unread = lambda r: [(i, (i + r) % n) for i in range(n) if (i + r) % n in free
                        and match.label_numbers(a[i]) not in nums((i + r) % n)]
    matters = lambda i, j: numbers_matter(a[i], codes.get(j), walked, readings or {}, own)
    misread = lambda r: next(((i, j) for i, j in unread(r) if matters(i, j)), None)
    kept = [r for r in found if misread(r) is None]
    if not kept:
        i, j = misread(found[0])
        return (f"reads at an icon place numbers the camera never read for that function ({a[i]!r} where the walked "
                f"list reads {b[j]!r}): another function, or its icon read yet another way")
    if excused is not None:
        excused.update((a[i], b[j]) for r in kept for i, j in unread(r))
    if not readings:
        return ("cannot be checked for a function outside the walked list: the table walk's picker screens gave no "
                "function readings")
    whys = [stands_for_other(a, b, r, codes, walked, readings, memo, own_readings=own_readings, alike=alike)
            for r in kept]
    if all(i is not None for i in whys):
        i = whys[0]
        return (f"reads, at some place, nearer a function outside the walked list than the walked one there (it may "
                f"offer another set of functions): {a[i]!r} where the walked list reads {b[(i + kept[0]) % n]!r}")
    return None


def state(row: str) -> str | None:
    """The state a report row was made in, its context ("Movie mode" of "... [Movie mode]"), None for none."""
    m = CONTEXT.search(row)
    return m[0][2:-1] if m else None


def walked_cells(tables: dict, screen: str) -> dict:
    """{the report's row name: (the walked cell, its page's title or its row's label)} of one screen of the table walk
    (runs/<camera>/kit2_tables/tables.json, `screen` its key there): every cell, key or tile the walk saw
    (match.walked_rows names them as the report names its rows). {} for a screen the file does not hold."""
    t = tables.get(screen) or {}
    # each cell's page title (a keyset's) or row label (a table's or a Fn menu's), by the cell itself
    where = {id(it): page.get("title") or "" for page in t.get("pages") or [] for it in page.get("items") or []}
    where.update({id(c): c.get("row_label") or "" for c in t.get("cells") or []})
    return {row: (item, where.get(id(item), "")) for row, item in match.walked_rows(tables, screen).items()}


def kept_codes(s: dict, codes: frozenset, held: set, report: list, factory: dict, name: str) -> set:
    """The codes one covered setting's list keeps: its picker's walked `codes` and the values the camera holds though
    the list cannot choose them (`held`), once its list and what the camera holds are seen to agree with them: NotCut
    when the setting does not list every walked code or the definition's sample does not hold it; the write stopped
    (exit 1, nothing written) when a proof (a report row's, or its proof as the pass holds it) or the sample holds a code
    outside them, for the walks and the camera then disagree, and a value the camera holds is never taken out. The
    words name the setting and the row, never the value."""
    k, keep = s["key"], set(codes) | set(held)
    if k not in factory:
        raise NotCut(f"the definition's sample does not hold {k}")
    lacking = codes - {v for v, _ in s.get("values") or []}
    if lacking:
        raise NotCut(f"{k} does not list every code its walks wrote ({len(lacking)} missing)")
    proofs = {(e["row"], v) for e in report for v in ((e["records"].get(k) or {}).get("proved") or {}).values()
              if isinstance(v, int) and not isinstance(v, bool)}
    proofs |= {("its proof as the pass holds it", v) for v in (s.get("proved") or {}).get("values") or ()}
    stray = sorted({row for row, v in proofs if v not in keep})
    if stray or factory[k] not in keep:
        where = f"a proof ({stray[0]})" if stray else "the definition's sample"
        sys.exit(f"walked lists: {k} ({s['name']}): {where} holds a code the walked list of its picker ({name}) leaves "
                 "out: the walks and the camera disagree, and a value the camera holds is never taken out. Look at the "
                 "walks and the hand table (PICKER_LISTS, or a NOT_OFFERED mark saying the camera holds it, held); "
                 "nothing written")
    return keep


def walked_lists(doc: dict, entries: dict, report: list, tables: dict, factory: dict | None,
                 held: dict | None = None, proofs: list | None = None, run_root: Path | None = None) -> tuple:
    """Each picker's list cut to its walks (the hand tables' PICKER_LISTS, `entries` by name, each with its hand
    evidence): every setting an entry covers lists exactly the codes its picker's walks wrote (walked_list, `proofs`
    the proof lines the report counts), the values a first kit gave it from a union of the camera's pickers taken out,
    each setting said with how many. A value the camera writes itself though its list cannot choose it (a NOT_OFFERED
    mark's `held` value, `held`: {key: values}) is never taken out. An entry whose evidence fails leaves its settings'
    lists as they are, said, as a refused not-offered mark is. A value a proof wrote for a covered setting (the report's
    rows, or its proof as the pass holds it), or that the definition's sample holds (`factory`: {key: value},
    sample_values; None when the definition has no sample, which refuses every entry, for nothing then shows the
    factory values are on the list), outside the walked codes stops the write (exit 1, nothing written); and so does
    one the camera's own downloads hold in a cut setting's live record (check_cut_downloads, `run_root` the camera's
    runs; None, or no downloads there, said and not checked): the walks and the camera disagree, and no value the camera
    holds is dropped. Returns (values taken out, entries refused, {key: values taken out})."""
    held = held or {}
    gone, refused, said, vocabulary = {}, [], [], []
    readings = picker_readings(tables, report, proofs) if entries else {}
    for name, entry in entries.items():
        try:
            codes, covered = walked_list(name, entry, doc, report, tables, proofs, readings, vocabulary)
            if factory is None:
                raise NotCut("the definition has no sample, so nothing shows its factory values are on the walked list")
            plan = [(s, kept_codes(s, codes, set(held.get(s["key"]) or ()), report, factory, name)) for s in covered]
        except NotCut as why:
            refused.append((name, str(why)))
            continue
        for s, keep in plan:
            before = len(s.get("values") or [])
            s["values"] = [pair for pair in s.get("values") or [] if pair[0] in keep]
            gone[s["key"]] = before - len(s["values"])
            said.append((s["key"], s["name"], gone[s["key"]], len(s["values"]), name))
    print(f"walked lists: {sum(gone.values())} values the pickers never offer taken out of "
          f"{sum(1 for n in gone.values() if n)} settings, by {len(entries) - len(refused)} lists walked whole; "
          f"{len(refused)} refused")
    for k, sname, n, left, name in said:
        print(f"  walked list  {k} {sname[:44]}: {n} taken out, {left} left ({name})")
    for name, why in refused:
        print(f"  not cut  {name}: {why}")
    for line in vocabulary:
        print(line)
    if gone:
        check_cut_downloads(doc, sorted(gone), run_root)
    return sum(gone.values()), len(refused), gone


def check_cut_downloads(doc: dict, keys: list, run_root: Path | None, most: int = None) -> tuple | None:
    """Every setting a walked list was cut for (`keys`) against the camera's own downloads (downloads_by_system: up to
    SYSTEM_SAMPLE of each video system the download log lists, as check_video_systems reads them): a download the
    camera wrote that holds, in a cut setting's live record, a code its list no longer lists stops the write (exit 1,
    nothing written, the setting and the file named, never the value), for the camera holds it and the walks say the
    list cannot. A download that cannot be read is skipped and counted. With no runs here (`run_root` None, or no
    downloads in its log) it says so and checks nothing. Returns (downloads read, could not be read), or None."""
    from camkit import camset
    by, unread = downloads_by_system(run_root, most or SYSTEM_SAMPLE) if run_root is not None else ({}, 0)
    if not by:
        print("walked lists: no camera downloads on this computer to check the cut lists against, not checked")
        return None
    by_key = {s["key"]: s for s in doc["settings"]}
    lists = {k: {v for v, _ in by_key[k].get("values") or []} for k in keys if k in by_key}
    read = 0
    for files in by.values():
        for f in files:
            try:
                got = live_values(camset.read(f), lists)
            except (ValueError, OSError):
                unread += 1
                continue
            read += 1
            for k, v in sorted(got.items()):
                if v not in lists[k]:
                    sys.exit(f"walked lists: {k} ({by_key[k]['name']}) is cut to its picker's walked list, but "
                             f"{f.relative_to(run_root)}, a download the camera wrote, holds a code that list leaves "
                             "out in its live settings: the walks and the camera disagree, and a value the camera "
                             "holds is never taken out. Look at the walks and the hand table (PICKER_LISTS, or a "
                             "NOT_OFFERED mark saying the camera holds it, held); nothing written")
    print(f"walked lists: {len(lists)} cut settings checked against {read} of the camera's downloads"
          + (f", {unread} that could not be read skipped" if unread else ""))
    return read, unread


def cut_to_walks(doc: dict, entries: dict, not_offered: list, report: list, tables: dict, sample, proofs: list | None,
                 run_root: Path | None) -> tuple:
    """walked_lists as either pass calls it: the values each NOT_OFFERED mark says the camera holds (held) kept, the
    sample's values of the settings the entries cover read from `sample` (the definition's sample file,
    sample_values), the camera's downloads in `run_root` checked after the cut. `entries` carry their hand evidence."""
    held = {}
    for entry in not_offered:
        if entry.get("held"):
            held.setdefault(entry["key"], set()).update(entry["values"])
    covered = [s["key"] for s in doc["settings"] if any(re.search(e["keys"], s["key"]) for e in entries.values())]
    return walked_lists(doc, entries, report, tables, sample_values(sample, covered), held, proofs, run_root)


def table_cells(tables: dict, name: str, page: str | None) -> list:
    """The picker cells of one screen of the table walk (runs/<camera>/kit2_tables/tables.json): a keyset's page by
    its title ("Dial/Wheel"), or a table's own cells (My Dial Settings). None found: []."""
    t = tables.get(name) or {}
    if page is None:
        return [c for c in t.get("cells") or [] if c.get("opens") == "picker"]
    return [c for p in t.get("pages") or [] if p.get("title") == page for c in p.get("items") or []
            if c.get("opens") == "picker"]


def walked_rows(report: list, key: str, pattern: str) -> list:
    """The report's rows whose name matches `pattern` and that prove `key`: the walks of its list in each state. A
    row that chose only a sample of a picker stepped from the option the camera held ("sampled_from_start") walked no
    list, and is none of them."""
    return [e for e in report if walk_matches(pattern, e["row"]) and key in e["records"]
            and not e["records"][key].get("sampled_from_start")]


def twin_walks(report: list, key: str, pattern: str, tables: dict, proofs: list | None = None,
               readings: dict | None = None) -> list:
    """[(row, its records)] of the report's rows matching `pattern` that walked another key's or slot's picker whole,
    where the table walk shows `key`'s picker lists the same functions in the same order, numbers alike but at the
    twin's icon places, and no label reading nearer a function outside the twin's walked list than the walked one
    there (differs: icon_places and walk_codes from the twin's row, each record it walked whole, its codes and its
    screen, `proofs` the proof lines the report counts, none giving no icon place; `readings` the functions the camera
    has, picker_readings, read here when None): a key whose
    own row is a sample has its list walked on its twin (a movie Center Button's on the Multi-Slc Center Button's).
    `key`'s picker is found through its own rows, those that prove it and none of the records the twin's row walked (a
    row writing `key` along with the twin's own is no cell of `key`'s), each the table walk's cell it names
    (walked_cells), and every list involved went round to its start ("wrapped"); a twin's row chose a whole list, no
    sample from the held option, as many names and distinct codes as its list has places, and with `proofs` its proof
    lines chose every place of it (walk_problem, as walked_list holds a walk to). Without proofs no readings show the
    cells offer no other function, and no twin stands. [] when none does."""
    cells, screen_of = {}, {}
    for name in tables:
        got = walked_cells(tables, name)
        cells.update(got)
        screen_of.update(dict.fromkeys(got, name))
    base = lambda row: CONTEXT.sub("", row)
    labels = lambda item: [o["label"] for o in item.get("options") or []]
    out = []
    for e in report:
        if key in e["records"] or not walk_matches(pattern, e["row"]) or base(e["row"]) not in cells:
            continue
        item = cells[base(e["row"])][0]
        n = len(labels(item))
        whole = {k: r for k, r in e["records"].items() if not r.get("sampled_from_start") and len(r["proved"]) == n
                 and len({v for v in r["proved"].values() if isinstance(v, int) and not isinstance(v, bool)}) == n}
        own = [cells[base(x["row"])][0] for x in report if key in x["records"] and base(x["row"]) in cells
               and not set(whole) & set(x["records"])]
        if not whole or not own or not item.get("wrapped") or not all(c.get("wrapped") for c in own):
            continue
        # with the proof lines, the twin's row chose every place of its list, as a walked list's walk does
        if proofs is not None and walk_problem(e["row"], item, proofs):
            continue
        # an icon place of every record the twin walked whole: each record's own codes, read on the twin's screen; and
        # each record's codes place by place, and its set, for the functions outside the list
        screen = screen_of[base(e["row"])]
        on_screen = code_readings(screen, report, tables, proofs)
        free = frozenset.intersection(*(icon_places(screen, e["row"], k, report, tables, proofs, on_screen)
                                        for k in whole))
        if readings is None:
            readings = picker_readings(tables, report, proofs)
        walks = []
        for k, r in whole.items():
            walked = frozenset(v for v in r["proved"].values() if isinstance(v, int) and not isinstance(v, bool))
            walks.append((walk_codes(e["row"], k, proofs, walked, n), walked, {}))
        if any(differs(labels(c), labels(item), free, codes, walked, readings, memo, on_screen)
               for c in own for codes, walked, memo in walks):
            continue
        out.append((e["row"], list(whole.values())))
    return out


def held_in(run_root: Path, files: list, key: str, value: int) -> bool:
    """Whether each download (a path in the camera's runs) holds `value` in the record `key` ("global:0x0dfa")."""
    from camkit import camset
    m = re.fullmatch(r"global:0x([0-9a-f]{4})", key)
    if not m or not files:
        return False
    for f in files:
        path = run_root / f
        rec = camset.read(path).get(0, int(m[1], 16)) if path.exists() else None
        if rec is None or rec.value() != value:
            return False
    return True


def why_not(entry: dict, s: dict, value: int, report: list, tables: dict, run_root: Path,
            proofs: list | None = None) -> str | None:
    """Why a mark does not stand (None when its evidence holds): the setting lacks the value; a walk wrote it, or no
    walk proves the record (nor walked its twin's picker whole, twin_walks, `proofs` the proof lines the report counts);
    a picker list was not walked round, or lists the function; a held value's downloads do not hold it."""
    labels = dict((v, lab) for v, lab in s.get("values") or [])
    if value not in labels:
        return "the setting has no such value"
    if "walk" in entry:
        rows = walked_rows(report, s["key"], entry["walk"])
        if rows:
            wrote = [e["row"] for e in rows if value in e["records"][s["key"]]["proved"].values()]
        else:
            twins = twin_walks(report, s["key"], entry["walk"], tables, proofs)
            if not twins:
                return (f"no row the report proves matches {entry['walk']!r}, nor walks whole a picker the table walk "
                        "shows lists the same functions")
            wrote = [row for row, records in twins if any(value in r["proved"].values() for r in records)]
        if wrote:
            return f"{wrote[0]} wrote it"
    if "table" in entry:
        cells = table_cells(tables, *entry["table"])
        if not cells:
            return f"the table walk has no picker list on {entry['table']}"
        if not all(c.get("wrapped") for c in cells):
            return f"a list on {entry['table']} was not walked round to its start"
        listed = [o["label"] for c in cells for o in c.get("options") or [] if alike(strip_icon(o["label"]), labels[value])]
        if listed:
            return f"{entry['table']} lists {listed[0]!r}"
    if entry.get("held") and entry.get("files") and not held_in(run_root, entry["files"], s["key"], value):
        return "a download it cites does not hold it"
    return None


def not_offered_marks(doc: dict, entries: list, report: list, tables: dict, run_root: Path,
                      proofs: list | None = None) -> tuple:
    """Each setting's `not_offered`, [{value, label, why, menu, evidence, held?}] in value order, from the marks
    `entries` names (the hand tables' NOT_OFFERED: a key, its values, the why in plain words, the menu, the
    evidence, and
    "walk" (a pattern for the report's rows that walked the list, whole as the entry's evidence says: the writer checks
    that each proves the record, none chose only a sample of a picker, and none wrote the value; where none proves it, a
    row that walked whole a picker the table walk shows lists the same functions as the record's own, twin_walks, its
    icon places read from `proofs`, the proof lines the report counts),
    "table" (a picker screen of the table walk) or both), each
    written only when its evidence holds (why_not); a mark it refuses is printed. A value the camera holds but its list
    cannot choose back is "held" (ISO AUTO Minimum's factory ISO 64), and an editor keeps offering it. A setting no
    mark names loses an old field. Returns (values marked, marks refused)."""
    by_key = {s["key"]: s for s in doc["settings"]}
    marks, refused = {}, []
    for entry in entries:
        s = by_key.get(entry["key"])
        for v in entry["values"]:
            why = "no such setting" if s is None else why_not(entry, s, v, report, tables, run_root, proofs)
            if why:
                refused.append((entry["key"], v, why))
                continue
            mark = {"value": v, "label": dict((x, lab) for x, lab in s["values"])[v], "why": entry["why"],
                    "menu": entry["menu"]}
            if entry.get("evidence"):               # the hand evidence's (writer/hand_evidence.py), when it is here
                mark["evidence"] = entry["evidence"]
            if entry.get("held"):
                mark["held"] = True
            marks.setdefault(s["key"], {})[v] = mark
    for s in doc["settings"]:
        got = [m for _, m in sorted((marks.get(s["key"]) or {}).items())]
        if got:
            s["not_offered"] = got
        else:
            s.pop("not_offered", None)
    n = sum(len(m) for m in marks.values())
    print(f"not offered: {n} values the camera's menus never offer, on {len(marks)} settings "
          f"({sum(1 for m in marks.values() for x in m.values() if x.get('held'))} of them held, still offered); "
          f"{len(refused)} marks refused")
    for k, v, why in refused:
        print(f"  not marked  {k} {v}: {why}")
    return n, len(refused)


# a proof's context that names the video system its row was walked under ("Movie mode, PAL, File Format XAVC S 4K")
SYSTEM_WORD = re.compile(r"\[[^\]]*\b(NTSC|PAL)\b[^\]]*\]")


def proof_file(run_root: Path, run: Path, dat: str) -> Path | None:
    """A proof's download: one named with its run in front (pass2_report.qualified) in that run's dat/ or at its top,
    else in the main run's dat/."""
    from pass2_report import QUALIFIED
    m = QUALIFIED.fullmatch(dat or "")
    places = [run_root / m[1] / "dat" / m[2], run_root / m[1] / m[2]] if m else [run / "dat" / (dat or "")]
    return next((p for p in places if dat and p.exists()), None)


def row_systems(report: list, proofs: list, run_root: Path, run: Path) -> dict:
    """{report row: its video system} for each row of a record some row's context walked under a named video system
    (SYSTEM_WORD): the system every download of the row's proofs says in its header (camkit.camset's video_system),
    and the context's word, where it names one, agreeing. A row whose downloads say two systems, none, or another than
    its context is printed and left out."""
    from camkit import camset
    from pass2_report import row_name
    named = {k for e in report if SYSTEM_WORD.search(e["row"]) for k in e["records"]}
    rows = {e["row"] for e in report if set(e["records"]) & named}
    files = {}
    for r in proofs:
        if row_name(r) in rows and r.get("dat"):           # an option drawn grey that was never tried has no download
            files.setdefault(row_name(r), []).append(proof_file(run_root, run, r.get("dat")))
    out, seen = {}, {}
    for row in sorted(rows):
        said = set()
        for f in files.get(row) or [None]:
            if f is not None and f not in seen:
                seen[f] = camset.read(f).video_system
            said.add(seen.get(f) if f is not None else None)
        word = SYSTEM_WORD.search(row)
        if len(said) == 1 and None not in said and (not word or word[1] in said):
            out[row] = said.pop()
        else:
            print(f"  video system  {row[:70]}: its downloads say {sorted(map(str, said))}"
                  + (f", its context {word[1]}" if word else "") + "; left out")
    return out


def system_values(doc: dict, report: list, systems: dict, table: dict) -> dict:
    """{key: {"NTSC": [...], "PAL": [...]}}: for each setting rows walked under each video system (row_systems), the
    listed values proved under one system only, in value order; a value proved under both is under neither, and so is
    one no proof walked. A setting gets one when some listed value is one system's: a list whose listed values are all
    one system's has the other's empty (the other system's rates, proved, not among its values). The camera's hand
    table (`table`, the hand tables' VIDEO_SYSTEM_VALUES: a key, its values by system, both keys, and the evidence)
    gives a
    setting no proof walked under both systems; where the proofs speak, they stand and the table's entry is printed."""
    by_key = {s["key"]: s for s in doc["settings"]}
    seen = {}
    for e in report:
        system = systems.get(e["row"])
        for k, r in e["records"].items() if system else ():
            seen.setdefault(k, {}).setdefault(system, set()).update(
                v for v in r["proved"].values() if not isinstance(v, (list, dict)))
    out = {}
    for k, by in seen.items():
        listed = [v for v, _ in (by_key.get(k) or {}).get("values") or []]
        ntsc, pal = by.get("NTSC", set()), by.get("PAL", set())
        got = {"NTSC": sorted(v for v in listed if v in ntsc - pal), "PAL": sorted(v for v in listed if v in pal - ntsc)}
        if "NTSC" in by and "PAL" in by and (got["NTSC"] or got["PAL"]):
            out[k] = got
    for k, entry in table.items():
        if k in out:
            print(f"  video system  {k}: the proofs give its values; the hand table's entry is not used")
        elif k in by_key:
            listed = {v for v, _ in by_key[k].get("values") or []}
            out[k] = {"NTSC": sorted(v for v in entry["NTSC"] if v in listed),
                      "PAL": sorted(v for v in entry["PAL"] if v in listed)}
    return out


def with_video_systems(doc: dict, report: list, proofs: list, table: dict, run_root: Path, run: Path) -> int | None:
    """Each setting's `video_system_values` ({"NTSC": [...], "PAL": [...]}: a value listed under one system is
    offered only when the file's header says that system; one under neither under both) from system_values, right
    after its `not_offered` or its values; a setting none is found for loses an old one. With no proofs (a plain run
    with no report) the definition is left as it is. Returns how many settings carry one."""
    if not proofs:
        return None
    found = system_values(doc, report, row_systems(report, proofs, run_root, run), table)
    for s in doc["settings"]:
        want = found.get(s["key"])
        fields = [(k, v) for k, v in s.items() if k != "video_system_values"]
        after = "not_offered" if "not_offered" in s else "values"
        s.clear()                                   # in place: the callers' by-key maps hold these very settings
        for k, v in fields:
            s[k] = v
            if k == after and want:
                s["video_system_values"] = want
        if want and "video_system_values" not in s:
            s["video_system_values"] = want
    print(f"video systems: {len(found)} settings whose menus offer some values under one video system only "
          f"({', '.join(sorted(found))})")
    return len(found)


# how many downloads of each video system the check reads, spread over the camera's download log
SYSTEM_SAMPLE = 200


# downloads_by_system's samples, by the runs folder, the sample's size and the download log as it stood (its size and
# time), so the write's two checks against the camera's downloads read the log's files once
_SAMPLES = {}


def downloads_by_system(run_root: Path, most: int = SYSTEM_SAMPLE) -> tuple:
    """({video system: [downloads]}, how many could not be read): up to `most` of the camera's downloads of each video
    system its header says (the download log, runs/<model>_fw<fw>/downloads.jsonl), spread evenly over each system's
    downloads, so the system with few downloads is read as widely as the other. Each download's header is read once
    while the log stays as it is (_SAMPLES): check_cut_downloads and check_video_systems share the sample."""
    log = run_root / "downloads.jsonl"
    stat = log.stat() if log.exists() else None
    key = (str(Path(run_root).resolve()), most, stat and (stat.st_size, stat.st_mtime_ns))
    if key not in _SAMPLES:
        _SAMPLES[key] = _sample_by_system(run_root, most)
    by, unread = _SAMPLES[key]
    return {vs: list(files) for vs, files in by.items()}, unread


def _sample_by_system(run_root: Path, most: int) -> tuple:
    """downloads_by_system's sample, read from the download log and each download's header."""
    from camkit import camset
    log = run_root / "downloads.jsonl"
    names = [json.loads(x)["path"] for x in log.read_text(encoding="utf-8").splitlines() if x.strip()] \
        if log.exists() else []
    by, unread = {}, 0
    for n in names:
        path = run_root / n
        try:
            by.setdefault(camset.peek_video_system(path.read_bytes()), []).append(path)
        except (ValueError, OSError):
            unread += 1
    # a file whose block does not say its system ("") says nothing of either list
    return {vs: files[::max(1, len(files) // most)][:most] for vs, files in by.items() if vs}, unread


def check_video_systems(doc: dict, run_root: Path, most: int = SYSTEM_SAMPLE) -> tuple | None:
    """Every setting's video_system_values against the camera's own downloads (downloads_by_system): a value listed as
    one system's only must not be held in the live settings of a download whose header says the other system, for the
    camera wrote that file and an editor would flag it. A contradiction stops the write (exit 1, the setting and the
    file named, never a value); a download that cannot be read is skipped and counted. Returns (downloads read, could
    not be read), None with no downloads."""
    from camkit import camset
    marked = [s for s in doc["settings"] if s.get("video_system_values")]
    by, unread = downloads_by_system(run_root, most)
    if not by:
        return None
    read = 0
    for system, files in sorted(by.items()):
        for f in files:
            try:
                cs = camset.read(f)
            except (ValueError, OSError):
                unread += 1
                continue
            read += 1
            for s in marked:
                other = [v for vs, vals in s["video_system_values"].items() if vs != system for v in vals]
                m = re.fullmatch(r"global:0x([0-9a-f]{4})", s["key"])
                rec = cs.get(0, int(m[1], 16)) if m else None
                if rec is not None and rec.value() in other:
                    sys.exit(f"video systems: {s['key']} ({s['name']}) lists a value as another system's only, but "
                             f"{f.relative_to(run_root)}, a {system} download, holds it: the proofs or the hand table "
                             "(VIDEO_SYSTEM_VALUES) are wrong for this camera; nothing written")
    print(f"video systems: {len(marked)} settings' values checked against {read} of the camera's downloads "
          f"({', '.join(f'{len(fs)} {vs}' for vs, fs in sorted(by.items()))})"
          + (f", {unread} that could not be read skipped" if unread else ""))
    return read, unread
