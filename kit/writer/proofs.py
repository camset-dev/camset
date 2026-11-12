"""A setting's evidence from the proofs: what a rerun keeps of the proof the definition held (kept_proof: a value a
counted line still wrote, written_values), what backs each value's name (proved.names), the option trees, a number the
camera shows scaled (shown_as), the old lists of the values camera files held taken out (without_observed), the marks
on the values no option was seen to write taken out (without_held), the records a proof wrote together taken out
(without_written_with), a list of numbers sampled on a line (sampled_scale), one code table for an array's slots
(one_slot_table), the mark on a record pass2_report found not one to one, a live setting's memory copy seen taken by a
registration (in_sets_proved), and the owner's allowance a proof carries in the note's evidence (with_allowances)."""
import collections
import json
import re
from pathlib import Path

from camkit import option_tree
from pass2_report import (carried_over, element_changes, linear, row_name, rows_of, sampled_from_start,
                          scale_number, stood_on)

from .labels import clean, squashed, value_order
from .notes import add_evidence


def sampled_scale(s: dict, codes) -> bool:
    """KIT_PLAN's line rule ("Sampling long number ranges") on a setting that lists its values (no range), the
    camera's side of it already found (the report's `linear`, from what the camera showed and stored; a hand table's
    word for a by-hand proof): every label a number of one unit (pass2_report.scale_number: "2500 K", "+5/6 EV",
    "12"), no number at two codes, fewer values proved than it lists (a list proved whole is no sample), at least three
    proved, the lowest and the highest number among them, and every value the list holds on the straight line through
    those two by its labels, so the values between are what the line says (Exposure Comp.'s list, thirds and halves
    between, is none).
    Such a scale is written sampled: the values between are inferred, and the proved ones are not listed, for one of
    them is the camera's own setting when the proofs began (docs/decisions/0016). White Balance's colour temperature
    (2500-9900 K, stored (K - 2500) / 100), Exposure Std. Adjust's sixths, Aspect Marker Level and Audio Rec Level are
    such scales."""
    vals = [(v, lab) for v, lab in s.get("values") or [] if isinstance(v, int)]
    if s.get("range") or not vals or len(vals) != len(s["values"]):
        return False
    read = {v: scale_number(lab) for v, lab in vals}
    if any(r is None for r in read.values()) or len({r[1] for r in read.values()}) != 1 \
            or len({r[0] for r in read.values()}) != len(read):
        return False                            # a word, two units, or one number at two codes (no line holds both)
    codes = {v for v in codes if v in read}
    if len(codes) < 3 or codes >= set(read):
        return False
    ends = {min(read, key=lambda v: read[v][0]), max(read, key=lambda v: read[v][0])}
    return ends <= codes and linear({read[v][0]: v for v in read}) is True


def linked_slots(slots: list, proved: dict, refused: dict) -> list:
    """The slots of one array that the camera shows one list for, in groups: two slots are linked when a value is
    proved alike in both (one code under one label), or when one slot's list refused a label the other proved, for a
    refusal names an option of the same list (PP1-PP6's Color Mode refuses BT.2020 and 709, which PP10 proved; PP10's
    refuses Movie, which PP1 proved). `refused`: key -> the labels the slot's rows refused. A slot linked to none is a
    group of its own."""
    pairs = {s["key"]: {(v, lab) for v, lab in s["values"] if v in proved[s["key"]] and not isinstance(v, (list, dict))}
             for s in slots}
    shown = {k: {squashed(lab) for _, lab in p} for k, p in pairs.items()}
    said = {s["key"]: {squashed(lab) for lab in refused.get(s["key"]) or ()} for s in slots}
    root = {s["key"]: s["key"] for s in slots}

    def top(k):
        while root[k] != k:
            k = root[k]
        return k
    keys = [s["key"] for s in slots]
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if pairs[a] & pairs[b] or said[a] & shown[b] or said[b] & shown[a]:
                root[top(a)] = top(b)
    parts = collections.defaultdict(list)
    for s in slots:
        parts[top(s["key"])].append(s)
    return list(parts.values())


def one_slot_table(doc: dict, proved: dict, derived: dict, changed: list, refused: dict | None = None) -> int:
    """The slots of one array record that carry one name (Picture Profile's Color Mode for PP1-PP11) share one code
    table when the camera shows them one list (linked_slots: a value proved alike in two, or a label one slot's list
    refused that another proved) and no two of their proofs disagree, a label for two codes or a code under two
    labels: a value proved in one slot is then named so in every other linked slot (source "derived"), and added where
    its values lack it (PP10's HLG2 gamma proved BT.2020 = 10 and 709 = 11, which the other gammas refuse,
    menu_blocked). Slots without a proof (PP7-PP9, off this body's menu) are left as they are, and so is a slot linked
    to none. Prints each record whose slots disagree, and each slot linked to none. Returns how many values it named
    afresh: added, relabelled, or with no source for their name before (a value a hand table or a reader names keeps
    that name, with_names; a rerun names none)."""
    groups = collections.defaultdict(list)
    for s in doc["settings"]:
        if s.get("index") is not None and proved.get(s["key"]) and s.get("values"):
            groups[(s["area"], s["id"], s["name"])].append(s)
    n = 0
    for (_area, rid, name), all_slots in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][2])):
        if len(all_slots) < 2:
            continue
        parts = linked_slots(all_slots, proved, refused or {})
        alone = [p[0]["key"] for p in parts if len(p) == 1]
        if alone:
            print(f"  one table  0x{rid:04x} {name!r}: {', '.join(alone)} share no proved value or refusal with another "
                  "slot, not lent")
        n += sum(slot_table(rid, name, p, proved, derived, changed) for p in parts if len(p) >= 2)
    return n


def slot_table(rid: int, name: str, slots: list, proved: dict, derived: dict, changed: list) -> int:
    """One group of linked slots (one_slot_table): each value proved in one named so in the others, unless two proofs
    disagree (printed, nothing lent). Returns how many values it named afresh."""
    n = 0
    code_of, label_of, clash = {}, {}, []
    for s in slots:
        labs = dict((v, lab) for v, lab in s["values"])
        for v in sorted(proved[s["key"]], key=value_order):
            lab = labs.get(v)
            if lab is None or isinstance(v, (list, dict)):
                continue
            if label_of.setdefault(v, lab) != lab or code_of.setdefault(lab, v) != v:
                clash.append((s["key"], v, lab))
    if clash:
        print(f"  one table  0x{rid:04x} {name!r}: the slots disagree ({clash[:3]}), not lent")
        return 0
    for s in slots:
        labs = dict((v, lab) for v, lab in s["values"])
        used = {lab: v for v, lab in labs.items()}
        was = (s.get("proved") or {}).get("names") or {}        # the definition's proof, before this run's
        for v, lab in label_of.items():
            if v in proved[s["key"]] or used.get(lab, v) != v:
                continue                    # proved here, or the slot names another value so
            n += labs.get(v) != lab or str(v) not in was
            if labs.get(v) != lab:
                changed.append((s["key"], s["name"], v, labs.get(v), lab))
                labs[v] = lab
            derived[s["key"]][v] = "derived"
        s["values"] = [[v, lab] for v, lab in sorted(labs.items(), key=lambda kv: value_order(kv[0]))]
    return n


def with_option_trees(doc: dict, run: Path, audit: bool = False) -> int | None:
    """Each setting's option tree from the run's pass-2 proofs (camkit.option_tree), right after its values; a setting
    they give none to loses an old one. Prints how many, and with audit every setting that gets one and every one that
    sits on a carousel row or has labels of the shape "Main: Sub" and gets none, with why. Returns how many trees, or
    None with no proofs in the run (the definition is left as it is: nothing a run does not show is written)."""
    proofs = option_tree.read_proofs(run)
    if not proofs:
        print(f"option trees: {run} holds no proofs, so the definition's are left as they are")
        return None
    shared_from = {}
    found, why_not = option_tree.trees(doc, proofs, shared_from)
    doc["settings"] = [option_tree.with_tree(s, found.get(s["key"])) for s in doc["settings"]]
    print(f"option trees: {len(found)} settings with the camera's nested options ({len(shared_from)} sharing another's, "
          f"of the same values); {len(why_not)} on a carousel row or with labels of the shape \"Main: Sub\" without one")
    if audit:
        names = {s["key"]: s["name"] for s in doc["settings"]}
        for k, got in found.items():
            print(f"  tree  {k} {names[k][:48]:48s} {option_tree.shown(got)}"
                  + (f" (shared with {shared_from[k]}, of the same values)" if k in shared_from else ""))
        for k, why in why_not.items():
            print(f"  none  {k} {names[k][:48]:48s} {why}")
    return len(found)


def kept_proof(old: dict | None, new: dict, gone: frozenset = frozenset(), written: frozenset = frozenset()) -> tuple:
    """(the proof to write, what of the old one the new one did not show): the report's proof, and of the one the
    definition held only the values a line the report reads still wrote (`written`, written_values: a change to that
    value in a line that counts, not carried over from the option before) that the report does not credit (a list's
    option numbered apart in two sessions, whose later line takes its place in the report: a hold's Shoot Mode). Never
    an old menu row, an old count of samples, or an old value no counted line wrote: a definition written over an older
    one says what the proofs say today, so a row the report leaves out (made where the camera stood, a side effect, a
    hand table's proof since replaced by the kit's) or a value an older rule credited (a start line, the option a
    session found) goes (docs/decisions/0016). `gone`: values only a start line accounted for (pass2_report.start_lines:
    a part walk's start or put-back), never kept even if written. No "inferred" is written: a definition never marks
    which values no option was seen to write. A proof of another kind (values where there were samples) is the new
    one."""
    new = {k: v for k, v in new.items() if k != "inferred"}
    if not old or ("values" in old) != ("values" in new) or ("sampled" in old) != ("sampled" in new):
        return new, []
    out, said = dict(new), []
    if old.get("names"):
        out["names"] = old["names"]          # what backed each name, for the values kept (with_names)
    if "values" in new:
        values = (set(old["values"]) - set(new["values"]) - set(gone)) & set(written)
        out["values"] = sorted(set(new["values"]) | values)
        if values:
            said.append(f"{len(values)} values")
    return out, said


def written_values(proofs: list, skip: set, reported=None) -> dict:
    """{key: the values the proof lines the report counts wrote to it}: each line not cut short (skip, as
    pass2_report.report_proofs gives it), not left out as made where the camera stood (stood_on, `reported` the rows
    of the report the writer reads), not of a row sampled from the option the camera held (sampled_from_start: its
    values are a count, never listed, decision 16), applied and planned, each change to a record or an array's slot
    (element_changes) but one carried over from the option before (carried_over). kept_proof keeps an old value only
    among these."""
    left = set(skip) | stood_on(proofs, skip, reported)
    carried = {(c["dat"], c["key"]) for c in carried_over(proofs, left)}
    from_start = {name for name, opts in rows_of(None, proofs, left).items() if sampled_from_start(opts)}
    out = collections.defaultdict(set)
    for i, r in enumerate(proofs):
        if i in left or r.get("applied") is False or r.get("planned") is False or row_name(r) in from_start:
            continue
        slots = element_changes(r) if "changes" in r or r.get("proof") == "display" else []
        for c in list(r.get("changes") or []) + slots:
            if (r.get("dat"), c.get("key")) not in carried and isinstance(c.get("after"), (int, str)):
                out[c["key"]].add(c["after"])
    return dict(out)


def print_kept(kept: dict, by_key: dict) -> None:
    """Every setting whose proof keeps a value the report did not credit (kept_proof), and how many: a person sees
    where the report and the definition part."""
    kept = {k: said for k, said in kept.items() if said}
    if not kept:
        return
    print(f"kept from the definition: {len(kept)} settings hold values a counted proof line wrote that this report "
          f"does not credit (kept_proof)")
    for k, said in sorted(kept.items()):
        print(f"  kept  {k} {by_key[k]['name'][:44]:44s} {', '.join(said)}")


def mixed(record: dict) -> bool:
    """pass2_report found the record's labels and values not one to one: nothing of it is applied."""
    return any(n.get("kind") == "not one to one" for n in record.get("notes") or [])


# where each value's name comes from (proved.names, schemas/definition.schema.json): read off the camera by two
# readers, one, or the vision model alone; the old schema's label kept by likeness; a hand table's; copied from a
# sibling, a hold or a bracket by a rule; a number scale's value between the sampled points. A value taken from
# "nothing changed" has its readers' source like any other, never a mark of its own (docs/decisions/0016), and an old
# source of that kind ("held") is not written again (with_names)
NAME_SOURCES = ("two readers", "one reader", "vision model", "schema kept", "hand table", "counted", "derived",
                "sampled")
READER_RANK = ("two readers", "one reader", "vision model")


def reader_source(said) -> str:
    """pass2_report's word for what backs a name (`names`: "two readers", "one reader (map)", "ocr disagrees",
    "disputed", a carousel's or a box's own reading...) in proved.names' words: two readers or the vision model alone
    as said; every other single reading, a disputed one among them (the map's label stood), one reader, and so is an
    older report's "held" (the label was read off the screen, whatever else backed it)."""
    return said if said in ("two readers", "vision model") else "one reader"


def note_readers(readers: dict, k: str, r: dict) -> None:
    """Each value a report record proves, with what backs its name (its `names`), the best when several rows prove it
    (READER_RANK). The record's `inferred` labels (taken from "nothing changed") count as any other: one is the row's
    start (docs/decisions/0016)."""
    names = r.get("names") or {}
    for lab, v in (r.get("proved") or {}).items():
        if isinstance(v, (list, dict)):
            continue
        src = reader_source(names.get(str(lab)))
        was = readers[k].get(v)
        if was is None or READER_RANK.index(src) < READER_RANK.index(was):
            readers[k][v] = src


def with_names(s: dict, readers: dict, over: dict, derived: dict) -> None:
    """The setting's proved.names, {"<value>": source} (NAME_SOURCES): every proved value, the hand table's or the
    kept schema label's where one named it against the reading (`over`), else the readers', else what the definition
    said before (a value kept_proof keeps), else a rule's copy (`derived`), else one reader; and each other value a rule
    or a hand table named, or a sampled scale's, as such. Nothing when the setting has no proof. A source the
    definition said before that is no longer one ("held", docs/decisions/0016) is not kept, nor an old reading of a value
    a picker's sample from the held option proved (its proof now a count, "from_start")."""
    p = s.get("proved")
    if not p:
        return
    old = {v: src for v, src in (p.get("names") or {}).items() if src in NAME_SOURCES}
    seen = set(p.get("values") or ())
    # a scale's samples name its values between "sampled"; a sample stepped from the option the camera held (a picker's
    # three, "from_start") names nothing, its values named by the slot proved in full or not at all
    line = "sampled" in p and not p["sampled"].get("from_start")
    out = {}
    for v in sorted(seen | {v for v, _ in s.get("values") or [] if not isinstance(v, (list, dict))}, key=value_order):
        if v in seen:
            src = over.get(v) or readers.get(v) or old.get(str(v)) or derived.get(v) or "one reader"
        else:
            src = over.get(v) or derived.get(v) or ("sampled" if line else None) \
                or (old.get(str(v)) if old.get(str(v)) in ("derived", "sampled", "schema kept", "hand table") else None)
        if src:
            out[str(v)] = src
    p.pop("names", None)
    if out:
        p["names"] = out


# a number the camera shows scaled (Knee Point "75%" stored 7500): the scales tried, and a shown number with its unit
SCALES = (10, 100, 1000)
SHOWN_NUMBER = re.compile(r"^\s*([+-]?\d+(?:\.(\d+))?)\s*(%|[A-Za-z]{1,4})?\s*$")


def scaled_numbers(proofs: list, doc: dict) -> dict:
    """{key: {"divide", "decimals", "unit"}} for each number setting (a range) whose side-list or field proofs all show
    a number that, times one scale of SCALES, is the stored value (two or more numbers but 0 among them): the camera
    shows "75%" and stores 7500. decimals as the camera's text shows them, unit the text's ("%", "mm"). A record
    array's elements no proof reached take their record's scale when every proved element agrees and they share its
    range and step (PP7-PP9, off this body's menu)."""
    by_key = {s["key"]: s for s in doc["settings"]}
    seen = collections.defaultdict(list)
    for r in proofs:
        if r.get("kind") not in ("sidelist", "fields") or r.get("applied") is False or not isinstance(r.get("shown"), str):
            continue
        for c in r.get("changes") or []:
            a, b = c.get("after"), c.get("before")
            if isinstance(a, list):
                moved = [i for i, (x, y) in enumerate(zip(a, b or [])) if x != y]  # noqa: B905 (missing before means nothing moved)
                if len(moved) != 1:
                    continue
                seen[f"{c['key']}[{moved[0]}]"].append((r["shown"], a[moved[0]]))
            else:
                seen[c["key"]].append((r["shown"], a))
    found = {}
    for k, pairs in seen.items():
        s = by_key.get(k)
        if s is None or not s.get("range"):
            continue
        parsed = [(SHOWN_NUMBER.match(t), v) for t, v in pairs]
        if not all(m and isinstance(v, (int, float)) for m, v in parsed):
            continue
        numbers = {float(m[1]) for m, _ in parsed}
        if len(numbers - {0.0}) < 2:
            continue
        fits = [n for n in SCALES if all(abs(float(m[1]) * n - v) < 1e-6 for m, v in parsed)]
        units = {m[3] or "" for m, _ in parsed}
        if len(fits) != 1 or len(units) != 1:
            continue
        found[k] = {"divide": fits[0], "decimals": max(len(m[2] or "") for m, _ in parsed), "unit": units.pop()}
    by_record = collections.defaultdict(list)
    for k, info in found.items():
        by_record[k.split("[")[0]].append((k, info))
    for rec, got in by_record.items():
        if "[" not in got[0][0] or len({json.dumps(i, sort_keys=True) for _, i in got}) != 1:
            continue
        like = by_key[got[0][0]]
        for s in doc["settings"]:
            if s["key"].startswith(rec + "[") and s["key"] not in found and s.get("range") == like.get("range") \
                    and s.get("step") == like.get("step"):
                found[s["key"]] = got[0][1]
    return found


def with_shown_as(s: dict, info: dict | None) -> dict:
    """The setting with "shown_as": {"divide", "decimals"} right after its unit (or range and step), and its unit from
    the camera's text when it had none; without shown_as when info is None."""
    out = {k: v for k, v in s.items() if k != "shown_as"}
    if not info:
        return out
    if not out.get("unit") and info["unit"]:
        out["unit"] = info["unit"]
    after = "unit" if "unit" in out else "step" if "step" in out else "range"
    res = {}
    for k, v in out.items():
        res[k] = v
        if k == after:
            res["shown_as"] = {"divide": info["divide"], "decimals": info["decimals"]}
    return res


def shown(value: int, shown_as: dict) -> str:
    """A stored number as the camera shows it (7500 with divide 100: "75"), the arithmetic the editor does."""
    return f"{value / shown_as['divide']:.{shown_as['decimals']}f}"


def with_scales(doc: dict, run: Path) -> int | None:
    """Every number setting's shown_as from the run's proofs (scaled_numbers): a setting they give none loses an old
    one. Untouched when the run has no proofs. Returns how many."""
    proofs = option_tree.read_proofs(run)
    if not proofs:
        return None
    found = scaled_numbers(proofs, doc)
    doc["settings"] = [with_shown_as(s, found.get(s["key"])) for s in doc["settings"]]
    print(f"shown as: {len(found)} number settings the camera shows scaled, divided by "
          f"{sorted({info['divide'] for info in found.values()})}")
    return len(found)


def axis_value_rows(proofs: list) -> frozenset:
    """The carousel axis rows (pass2_report names one "<item> / <option>") whose option is no option owning the axis
    but the value the axis stood on when the row was walked: the option is one of the axis's own labels. ISO AUTO Min.
    SS's speeds are one line of values, Slower to Faster, and its row took the name of the one it stood on; Focus
    Area's Custom 1-3 likewise. Spot's sizes ("Spot: <size>") are an axis Spot owns, and keep their row's name. The option
    and the labels are compared as the camera's words, OCR slips mended and case aside (clean), as the reader may
    spell one and the bar the other. Returns {(item, option)}, the item its path joined by " > "."""
    labels = collections.defaultdict(set)
    for r in proofs:
        if r.get("kind") == "axis" and r.get("option"):
            labels[(" > ".join(r.get("path") or []), r["option"])].add(clean(str(r.get("label"))).lower())
    return frozenset(k for k, labs in labels.items() if clean(k[1]).lower() in labs)


AXIS_ROW = re.compile(r"(.*?) / ([^\[]*?)( \[.*\])?")
# a proof context that says its state was found, not set ("stills, as found"): a run says nothing of a state it did not
# set (decision 16), for any camera; the item that says it goes with the state it names, and a context of nothing else
# goes whole
FOUND_WORDS = re.compile(r"\bas[\s-]+found\b", re.I)
AS_FOUND = re.compile(r"\s*\[([^\]]*\bas[\s-]+found\b[^\]]*)\]", re.I)
# a proof's context in other words ({pattern: words}), filled by the camera's writer from its tables
# (kit/schema_update.py: a1_tables.CONTEXT_WORDS): a context reworded in the runs after a definition kept its row, or a
# state as found that a proof does not need, which the runs still hold. Renamed where a row enters the definition and
# in the rows a definition kept, so the old words go (docs/decisions/0016)
CONTEXT_WORDS: dict = {}


def menu_row(row: str, axis_values: frozenset) -> str:
    """A proof row's name as the definition says it (proved.menu): an axis row named after the value the axis stood on
    (axis_value_rows) is named by its item alone, its context kept ("ISO AUTO Min. SS / <value> [ctx]" is "ISO AUTO
    Min. SS [ctx]"), for that value was the camera's own setting when the row began (docs/decisions/0016); a context
    the runs reworded (CONTEXT_WORDS) in its new words; and no context saying its state was found (AS_FOUND)."""
    m = AXIS_ROW.fullmatch(row)
    row = m[1] + (m[3] or "") if m and (m[1], m[2]) in axis_values else row
    for pattern, words in CONTEXT_WORDS.items():
        row = re.sub(pattern, words, row)
    return AS_FOUND.sub(not_found, row)


def not_found(context) -> str:
    """A proof context (AS_FOUND's match) without the item that says "as found" (any case, "as-found" too), the state
    it names with it ("Movie mode as found", "as found: Recording Media Slot 2", "Brightness Setup Manual (as found)"),
    and where those words are an item alone, the item before them, the state that was found ("Recording Media Slot 2,
    as found"): the other items in their brackets, or nothing."""
    items = [w.strip() for w in context[1].split(",") if w.strip()]
    drop = set()
    for i, w in enumerate(items):
        if FOUND_WORDS.search(w):
            drop.add(i)
            if FOUND_WORDS.fullmatch(w) and i:
                drop.add(i - 1)
    words = [w for i, w in enumerate(items) if i not in drop]
    return f" [{', '.join(words)}]" if words else ""


def with_menu_rows(doc: dict, axis_values: frozenset) -> int:
    """Every setting's proved.menu named as menu_row says: the passes name a proof's rows so as they take them in
    (before kept_proof, so a rerun's rows meet the definition's), and this renames what a definition kept from an
    older run; a rerun changes nothing. Prints and returns how many settings' kept rows were renamed."""
    n = 0
    for s in doc["settings"]:
        p = s.get("proved") or {}
        if not p.get("menu"):
            continue
        rows = sorted({menu_row(r, axis_values) for r in p["menu"]})
        if rows != p["menu"]:
            p["menu"] = rows
            n += 1
    print(f"menu rows: {len(axis_values)} axis rows named after the value they stood on, named by their item alone; "
          f"{n} settings' rows kept from an older run renamed; {len(CONTEXT_WORDS)} reworded-context patterns applied")
    return n


def without_observed(doc: dict, say: bool = True) -> int:
    """Every setting's old `observed` taken out (docs/decisions/0016). The lists came over from the old schema, built
    from the camera's downloads, so beside the proofs' values they held the owner's own settings (a dial's function,
    a key's, a memory's exposure mode); an editor reads what a proof established from `proved` itself (DATA_CONTRACTS,
    "What the editor offers outside Expert mode"). A field the definition held carries over to the next run, so this
    runs on every write: the full pass and the plain pass (printed, `say`), --option-trees, and from_data, which every
    write and --from-data end with. Returns how many settings lost one."""
    n = 0
    for s in doc["settings"]:
        if "observed" in s:
            del s["observed"]
            n += 1
    if say:
        print(f"observed: {n} settings' lists of the values camera files held taken out (an editor reads the proofs)")
    return n


def without_written_with(doc: dict) -> int:
    """Every setting's old `written_with` taken out (docs/decisions/0016): which records each proof wrote together is
    evidence, kept in pass 2's report for whoever maps the camera; in a definition, whatever rule pruned it, what was
    left told how the camera was set when the proofs were made (which of a family's copies a choice wrote). Runs on
    every write, in from_data, as without_observed. Returns how many settings lost one."""
    n = 0
    for s in doc["settings"]:
        if "written_with" in s:
            del s["written_with"]
            n += 1
    return n


def without_held(doc: dict) -> int:
    """Every setting's old `proved.inferred` and every name source "held" taken out: a definition never marks which
    values no option was seen to write (docs/decisions/0016). Such a value stays proved; a "held" name takes the source
    with_names gives it on a full write,
    "one reader" here (its label was read off the screen). Like without_observed it runs on every write, in from_data,
    which every write and --from-data end with, and --option-trees. Returns how many settings changed."""
    n = 0
    for s in doc["settings"]:
        p = s.get("proved") or {}
        names = p.get("names") or {}
        if "inferred" in p or "held" in names.values():
            p.pop("inferred", None)
            if names:
                p["names"] = {v: "one reader" if src == "held" else src for v, src in names.items()}
            n += 1
    return n


def disputed_out(doc: dict, keys: set) -> None:
    """A record pass2_report found not one to one keeps no proof: its old one goes, and it is marked "disputed" until a
    proof settles it; every other setting loses an old mark."""
    for s in doc["settings"]:
        if s["key"] in keys:
            if s.get("proved") or not s.get("disputed"):
                print(f"  disputed {s['key']} {s['name'][:50]}: not one to one in the report, its proof taken out")
            s.pop("proved", None)
            s["disputed"] = True
        else:
            s.pop("disputed", None)


def with_in_sets_proved(doc: dict, mirrors: dict) -> int:
    """Each live setting whose memory copy a registration was seen to take (pass2_report.registration_mirrors: kind
    "registration mirror", kit/provers/memreg_run.py) gets "in_sets_proved": {"run", "date", "slot"} right after
    "in_sets": the run, the day and the memory slot registered; a setting no line names loses an old one. A setting
    the definition does not keep in the sets (in_sets false) gets none, and is printed: the line would say otherwise.
    Keys, runs, days and slots only (docs/decisions/0016). Returns how many settings carry one."""
    n = 0
    for s in doc["settings"]:
        got = mirrors.get(s["key"])
        if got and not s.get("in_sets"):
            print(f"  in sets   {s['key']} {s['name'][:50]}: a registration took its copy, but the definition keeps it "
                  "out of the memory sets (in_sets false); not marked")
            got = None
        want = {"run": got["run"], "date": got["date"], "slot": got["slot"]} if got else None
        n += want is not None
        if s.get("in_sets_proved") == want and (want is None) == ("in_sets_proved" not in s):
            continue
        fields = [(k, v) for k, v in s.items() if k != "in_sets_proved"]
        s.clear()                                   # in place: the callers' by-key maps hold these very settings
        for k, v in fields:
            s[k] = v
            if k == "in_sets" and want:
                s["in_sets_proved"] = want
    return n


def with_allowances(doc: dict, allowed: dict) -> int:
    """The owner's allowances ({key: words}: "the owner allowed <row> remotely, <date>", a proof line's "allowance",
    runner.allowed_or_exit) in each setting's note evidence, once (add_evidence): a never-open row proved with the
    owner's word says so in Expert mode. Returns how many settings took words they lacked."""
    by_key = {s["key"]: s for s in doc["settings"]}
    n = 0
    for k, words in sorted(allowed.items()):
        s = by_key.get(k)
        for w in sorted(words) if s else ():
            n += add_evidence(s, w)
    return n
