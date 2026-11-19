"""Two settings the camera keeps in order, a lower limit and an upper one ("at_most" on the lower, "at_least" on the
upper; docs/DATA_CONTRACTS.md, "Two limits kept in order"): the a1 II's ISO Range Limit ends, its ISO AUTO Minimum and
Maximum. The camera never lets the lower sit past the upper: a value chosen past the other moves the other to it. The
camera's hand table names each pair (LIMIT_PAIRS in its hand tables file, writer/hand_tables.py), by the lower limit's
key, with each direction in which a proof showed the camera move the other limit; what proved it is the mapper's hand
evidence, which never reaches the definition. The order itself is checked here on the camera's own downloads at every
write, and a download that holds a pair out of order stops it. The order is each value's place in the two settings'
value lists, which must list the same values: never the codes', which need not rise with the value (decision 20).
Keys only, never a value (docs/decisions/0016)."""
import sys
from pathlib import Path

from .copies import SAMPLE, downloads, value_of

# the directions a LIMIT_PAIRS entry may say the camera moved the other limit in: the field on the entry, and the end
# whose definition field ("at_most" on the lower, "at_least" on the upper) carries moves_it for it
MOVES = (("lower_moves_upper", "at_most"), ("upper_moves_lower", "at_least"))


def pair_problem(lower: str, upper: str, by_key: dict, taken: set) -> str | None:
    """Why the hand table's pair `lower` <= `upper` cannot take effect in the definition (`by_key`, its settings by key;
    `taken`, the settings already a limit of a pair written before), in words, or None: both settings of the
    definition, two of them, each read as one number by its named values, the two listing the same values in the same
    order (codes and names: the order is their places), kept in the same sets, neither a limit of another pair."""
    if lower == upper:
        return "the two limits are one setting"
    for k in (lower, upper):
        if k not in by_key:
            return f"the definition lacks {k}"
    lo, up = by_key[lower], by_key[upper]
    for s in (lo, up):
        if not s.get("scalar") or len(s.get("values") or []) < 2:
            return f"{s['key']} is not a setting with named values"
    if [list(p) for p in lo["values"]] != [list(p) for p in up["values"]]:
        return "the two do not list the same values in the same order"
    if (lo.get("area"), bool(lo.get("in_sets"))) != (up.get("area"), bool(up.get("in_sets"))):
        return "the two are not kept in the same sets"
    for k in (lower, upper):
        if k in taken:
            return f"{k} is a limit of another pair already"
    return None


def place(s: dict, v) -> int | None:
    """Where value `v` stands in setting `s`'s value list, from 0; None for a value it does not list."""
    return next((i for i, (c, _) in enumerate(s.get("values") or []) if c == v), None)


def order_contradictions(files: list, pairs: list, by_key: dict) -> tuple:
    """({(lower key, upper key): (the first file, its section)} where a download holds the lower limit past the upper
    by their value lists' places, how many files read, how many could not be read, how many sections were checked).
    `pairs`: [(lower key, upper key)]. Every section both live in (the live settings for live settings, each memory set
    for settings the memories keep) whose records the file holds at values both lists name."""
    from camkit import camset
    bad, read, unread, checked = {}, 0, 0, 0
    for f in files:
        try:
            cs = camset.read(f)
        except (ValueError, OSError):
            unread += 1
            continue
        read += 1
        for lower, upper in pairs:
            lo, up = by_key[lower], by_key[upper]
            for section in range(len(cs.sections)):
                if not (section == 0 and lo.get("area") == "global" or section > 0 and (lo.get("in_sets") or lo.get("area") == "set")):
                    continue
                at = place(lo, value_of(cs, lower, section)), place(up, value_of(cs, upper, section))
                if None in at:
                    continue
                checked += 1
                if at[0] > at[1]:
                    bad.setdefault((lower, upper), (f, section))
    return bad, read, unread, checked


def with_limit_pairs(doc: dict, table: dict, run_root: Path | None = None, most: int = SAMPLE) -> int:
    """The hand table's pairs of limits the camera keeps in order (LIMIT_PAIRS: the lower limit's key, its upper, and
    the directions a proof showed the camera move the other) written as "at_most" on the lower, naming the upper, and
    "at_least" on the upper, naming the lower, each with "moves_it": true where the table says a value chosen past the
    other moved the other to it (MOVES), never else; every other setting losing an old one. A pair that cannot take
    effect (pair_problem: a setting the definition lacks, two that do not list the same values, one not read by named
    values, two kept in different sets, a setting already a limit of another pair) is printed, "not applied", and left
    out. With the camera's downloads (up to `most` of them, spread over its download log, as with_copies reads them),
    every section a download holds both in must hold the lower at or before the upper in their value lists: one that
    does not stops the write (exit 1, the pair, the file and the section named, nothing written), as with_copies stops
    it, for the hand table is then wrong for a state the camera wrote; a download that cannot be read is skipped and
    counted; with no downloads that is said and the pairs are written as the table gives them. The fields an entry's
    hand evidence adds (the ILCE-1M2's pass puts it back into the entries) are never written. Keys only, never a value
    a file held (docs/decisions/0016). Returns how many pairs are written."""
    by_key = {s["key"]: s for s in doc["settings"]}
    kept, taken = [], set()
    for lower, e in table.items():
        why = pair_problem(lower, e["upper"], by_key, taken)
        if why:
            print(f"  limit pair {lower} <= {e['upper']}: {why}; not applied")
            continue
        taken |= {lower, e["upper"]}
        kept.append((lower, e))
    files = downloads(run_root, most) if run_root is not None else []
    if kept and not files:
        print(f"limit pairs: no downloads {f'in {run_root}' if run_root is not None else 'given'} to check the order on; "
              "written as the hand tables give them")
    elif kept:
        bad, n, unread, checked = order_contradictions(files, [(lo, e["upper"]) for lo, e in kept], by_key)
        if bad:
            (lower, upper), (f, section) = sorted(bad.items(), key=lambda kv: kv[0])[0]
            sys.exit(f"limit pairs: {f.relative_to(run_root)}, section {section}, holds {lower} above {upper} by their "
                     "value lists" + (f" ({len(bad) - 1} more pairs contradicted)" if len(bad) > 1 else "")
                     + ": the camera's hand table (LIMIT_PAIRS) is wrong for a state the camera wrote, or the file is no "
                     "camera's; nothing written. Take the entry out of LIMIT_PAIRS, or prove the state that file shows, "
                     "then write again.")
        print(f"limit pairs: the lower at or below the upper in each of {checked} sections, of {n} downloads read"
              + (f", {unread} that could not be read skipped" if unread else ""))
    want = {}
    for lower, e in kept:
        for flag, field in MOVES:
            mine, other = (lower, e["upper"]) if field == "at_most" else (e["upper"], lower)
            want[mine] = (field, {"setting": other, **({"moves_it": True} if e.get(flag) is True else {})})
    for s in doc["settings"]:
        got = want.get(s["key"])
        for field in ("at_most", "at_least"):
            if got and got[0] == field:
                s[field] = got[1]
            else:
                s.pop(field, None)
    if kept:
        print(f"limit pairs: {len(kept)} pairs of limits the camera keeps in order")
    return len(kept)
