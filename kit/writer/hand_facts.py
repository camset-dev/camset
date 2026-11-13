"""A camera's hand tables put on its definition by the plain pass (writer/generic.py), the pass every camera's
definition takes but the ILCE-1M2 firmware 4.00's (docs/DATA_CONTRACTS.md, "The hand tables file"). The tables are
the camera's own, read without their evidence (writer/hand_tables.load_plain), every one optional: a camera with no
hand tables file, or with every table empty, gets the plain pass as it was before it read any.

What the plain pass reads (PLAIN): a record's name or note the camera proved wrong (RECORD_FIXES), records the menus
never write, found by hand (NEW_RECORDS, with FILTER_FLAGS' entries it takes in, laid out from the run's newest
download), a record a proof found laid out like a sibling (NEW_LIKE, NEW_WHOLE_LABELS), what a record holds and its
hand proof (FRAME_PROOFS), value names no proof gives (CAROUSEL, VALUE_FIXES, PP7_VALUES, KEEP_LABELS), the values the
menus never offer (NOT_OFFERED), the values offered under one video system (VIDEO_SYSTEM_VALUES), the copies (COPIES,
COPY_MODES, COPY_MODES_UNKNOWN), why a record cannot be proved (UNPROVED) and proof contexts in other words
(CONTEXT_WORDS). ZONE is a prover's (PROVERS). The rest the ILCE-1M2's own pass alone reads so far (A1_PASS_ONLY), or
no part of the kit's passes (NO_READER): the plain pass refuses a camera whose file fills one (refusals), in plain
words, for a mapper who fills in a table must not believe it took effect. Where an entry cannot take effect (a setting
the definition lacks, a value no setting lists) the pass says so, "not applied", as it goes.

A value a hand table names is named, not proved: its name's source is "hand table" (a name the editor offers) only
where a proof covers it (the report's, or a hand proof with its evidence) or a NOT_OFFERED mark says the camera holds
it; any other is "counted", which the editor offers in Expert mode only (named_not_proved), and a NEW_LIKE record's
fill from its sibling is established only where the sibling's value is (like_fill_names). What the tables or the hand
evidence no longer give goes: a record NEW_RECORDS added that the table no longer holds and no row names, a hand proof
whose evidence is gone and the copies' it lent them (new_records, frame_proofs), a reason's day and a mark's evidence
(unproved, not_offered: the write is told they went on purpose), each said.

How each hand fact was proved stays the mapper's (docs/decisions/0016), and the plain pass keeps it apart structurally:
the hand evidence (private/evidence/<model>_fw<fw>.hand.json) is never put into the tables, and each piece of it is
written only into a field the definition keeps as evidence (camkit.definitions.split): a hand proof's values, run, day
and menu rows into the setting's proof, a note's evidence ("note+") and the owner's word ("allowance") into
note_evidence, a reason's day into unproved_reason's date, what shows a not-offered mark into the mark's evidence. A
public note is the public table's note, word for word, whatever the evidence holds."""
import json
import re
import sys
from pathlib import Path

from camkit import paths

from .labels import clean
from .mirror import mirror_key, mirror_of
from .notes import ALLOWANCE, apply_fix, fix_differs
from .proofs import sampled_scale

# the tables the plain pass reads, in the order DATA_CONTRACTS lists them
PLAIN = ("RECORD_FIXES", "FILTER_FLAGS", "NEW_RECORDS", "NEW_LIKE", "NEW_WHOLE_LABELS", "FRAME_PROOFS", "CAROUSEL",
         "VALUE_FIXES", "PP7_VALUES", "KEEP_LABELS", "NOT_OFFERED", "VIDEO_SYSTEM_VALUES", "COPIES", "COPY_MODES",
         "COPY_MODES_UNKNOWN", "UNPROVED", "CONTEXT_WORDS")
# a table a prover reads for the camera it works on, which no pass of the writer reads
PROVERS = {"ZONE": "kit/provers/framepos_run.py --zone-grid"}
# the tables only the ILCE-1M2's own pass (kit/schema_update.py main) reads so far, each with what it is for: rules tied
# to that pass's own code (its checklist records, its Recall Custom holds, its My Menu, the first kit's spellings)
A1_PASS_ONLY = {
    "NEW_CHECK_NAMES": "the names of records a checklist first proves",
    "LATE_COPY": "the sentence a record a checklist first proves gets in its note",
    "EV_DOWN_FROM_20": "the Recall Custom holds' Exposure Comp. codes counted in quarter stops",
    "HOLD_TABLES": "a Recall Custom hold's copy of a live setting",
    "HOLD_BRACKET_COPIES": "a Recall Custom hold's bracket records",
    "ISO_TABLE": "the ISO Range Limit records' index into the ISO table",
    "LABEL_FIXES": "the first kit's OCR slips in the value names it wrote",
    "GROUP_NAMES": "the camera's names for menu groups the first kit read cut",
    "MY_MENU_ROW": "the row whose proofs add My Menu's items",
    "MY_MENU_EMPTY": "My Menu's empty place",
    "SHOOT_MODE_RECORDS": "the Shoot Mode carousel's descriptions, read with the camera's help",
    "ORIENTED": "the rows proved holding the camera one way",
}
# a table no pass reads: a test keeps the ILCE-1M2's notes in step with it
NO_READER = {"FRAME_STEPS": "the steps a press moved a focus frame, which only a test of the ILCE-1M2's notes reads"}
WHOLE = re.compile(r"(global|set):0x([0-9a-f]{4})")         # a whole record's key, no slot or block
LIVE = re.compile(r"global:0x([0-9a-f]{4})")                # a whole live record's key
# a hand proof's fields in the hand evidence (FRAME_PROOFS), and those it must name to be written
PROOF = ("proved", "sampled", "linear", "run", "date", "menu")
NEED = ("run", "date", "menu")
# the mark a hand proof carries in the definition's evidence (never public: camkit.definitions.lean_proof drops it), so
# a later run takes it out when the hand evidence no longer gives it
BY_HAND = "by_hand"


def refusals(tables) -> list:
    """Why the plain pass will not take the camera's hand tables as they stand, one line each, or []: a table it does
    not read filled (A1_PASS_ONLY, NO_READER), or an entry no table it reads would ever use (FILTER_FLAGS' entry no
    NEW_RECORDS $ref takes in, NEW_WHOLE_LABELS for no NEW_LIKE record, COPY_MODES without COPIES, a
    COPY_MODES_UNKNOWN family COPIES lacks), or a key the plain pass cannot lay a record out by (a NEW_RECORDS key that
    is no whole record, a NEW_LIKE key that is no whole live record). `tables`: writer/hand_tables.load's."""
    out = [f"{name} ({what}): read only by the ILCE-1M2's own pass so far" for name, what in A1_PASS_ONLY.items()
           if getattr(tables, name)]
    out += [f"{name} ({what})" for name, what in NO_READER.items() if getattr(tables, name)]
    taken = {k for k, e in tables.NEW_RECORDS.items() if e is tables.FILTER_FLAGS.get(k)}
    out += [f"FILTER_FLAGS' entry {k!r}: written only through NEW_RECORDS' {{\"$ref\": \"#/FILTER_FLAGS/{k}\"}}, which "
            "the file does not hold" for k in tables.FILTER_FLAGS if k not in taken]
    out += [f"NEW_WHOLE_LABELS' {k!r}: read only for a NEW_LIKE record, and NEW_LIKE does not hold it"
            for k in sorted(tables.NEW_WHOLE_LABELS) if k not in tables.NEW_LIKE]
    if tables.COPY_MODES and not tables.COPIES:
        out.append("COPY_MODES: read only with COPIES' families, and COPIES holds none")
    out += [f"COPY_MODES_UNKNOWN's {k!r}: read only for a COPIES family, and COPIES does not hold it"
            for k in sorted(tables.COPY_MODES_UNKNOWN) if k not in tables.COPIES]
    out += [f"NEW_RECORDS' {k!r}: a record found by hand is a whole record, \"global:0x....\" or \"set:0x....\""
            for k in tables.NEW_RECORDS if not WHOLE.fullmatch(k)]
    out += [f"NEW_LIKE's {k!r}: a record laid out like a sibling is a whole live record, \"global:0x....\""
            for k in tables.NEW_LIKE if not LIVE.fullmatch(k)]
    out += [f"NEW_LIKE's {' -> '.join(c)}: a cycle, each record laid out like the next, so none of them can be laid "
            "out first" for c in like_cycles(tables)]
    return out


def like_cycles(tables) -> list:
    """Each cycle of NEW_LIKE (a record laid out like one laid out like ... the first), as its keys in order, the first
    again at the end; one per cycle."""
    out, seen = [], set()
    for k in sorted(tables.NEW_LIKE):
        chain = [k]
        while tables.NEW_LIKE[chain[-1]][0] in tables.NEW_LIKE:
            nxt = tables.NEW_LIKE[chain[-1]][0]
            if nxt in chain:
                cycle = chain[chain.index(nxt):]
                if frozenset(cycle) not in seen:
                    seen.add(frozenset(cycle))
                    out.append([*cycle, nxt])
                break
            chain.append(nxt)
    return out


def like_order(tables) -> list:
    """NEW_LIKE's records in the order a pass lays them out and judges their fill: each after the record it is laid out
    like, where that one is a NEW_LIKE record too (a chain sibling first), else in key order; so the file's order
    changes nothing. A cycle never gets here (refusals)."""
    out, done = [], set()

    def visit(k, path):
        if k in done or k not in tables.NEW_LIKE or k in path:
            return
        visit(tables.NEW_LIKE[k][0], path | {k})
        done.add(k)
        out.append(k)
    for k in sorted(tables.NEW_LIKE):
        visit(k, frozenset())
    return out


def refusal_words(camera: str, why: list) -> str:
    """The plain pass's stop for refusals(): the file, each line, and what to do."""
    from camkit import datafiles
    return (f"schema_update: nothing done. {paths.shown(datafiles.hand_tables_file(camera))} holds what the plain pass, "
            f"which writes the {camera} definition, would not use, so it would change nothing there:\n"
            + "".join(f"  {w}\n" for w in why)
            + f"Take it out of the file (the plain pass reads {', '.join(PLAIN)}; docs/DATA_CONTRACTS.md, \"The hand "
              "tables file\"), then run the command again.")


def part(ev: dict, table: str, key) -> dict:
    """The hand evidence's fields for one entry (`ev`: writer/hand_tables.load_plain's, {table: {key: fields}})."""
    got = (ev.get(table) or {}).get(str(key) if table == "NOT_OFFERED" else key)
    return got if isinstance(got, dict) else {}


def hand_proofs(ev: dict) -> dict:
    """{key: its hand proof's fields} of the FRAME_PROOFS entries the hand evidence proves (values or a sample)."""
    return {k: {f: x for f, x in fields.items() if f in PROOF} for k, fields in (ev.get("FRAME_PROOFS") or {}).items()
            if isinstance(fields, dict) and {"proved", "sampled"} & set(fields)}


def hand_proof_gaps(ev: dict) -> list:
    """The FRAME_PROOFS entries whose hand proof (its values or sample, in the hand evidence) names no run, day or
    menu row there, each with what it lacks: the plain pass writes a hand proof only whole."""
    return [f"{k} (no {', '.join(f for f in NEED if not fp.get(f))})" for k, fp in hand_proofs(ev).items()
            if not all(fp.get(f) for f in NEED)]


def hand_proof_stop(camera: str, gaps: list) -> str:
    """Either pass's stop, before the definition is read and nothing written, on hand proofs whose run, day or menu
    row the hand evidence does not give (`gaps`, each key with what it lacks): what to add, and where."""
    from . import hand_evidence
    return (f"schema_update: nothing done. The hand evidence, {paths.shown(hand_evidence.path(camera))}, gives "
            f"hand proofs of FRAME_PROOFS without what the definition's evidence keeps of each: {'; '.join(gaps)}. "
            "A hand proof names the run it was made in, its day and its menu row (\"run\", \"date\" and \"menu\" "
            "beside its \"proved\" or \"sampled\"; docs/DATA_CONTRACTS.md, \"The hand evidence file\"): add them "
            "there, then run the command again.")


def _copy(x):
    return json.loads(json.dumps(x))


def run_start(run_root: Path, run: Path) -> Path:
    """The run's newest start file, by the camera's downloads manifest (camkit.provenance.newest_start): a new record's
    size, count and memory-set presence are read from it, and like_setting's fill asks whether its value is among the
    proofs. Until 2026-11-11 the file names sorted as text chose it, an old download ("93438_before.DAT" after
    "239606_before.DAT")."""
    from camkit import provenance
    got = provenance.newest_start(run_root, under=run)
    if got is None:
        sys.exit(f"no start file of {run.name} in the camera's downloads manifest "
                 f"({paths.shown(provenance.manifest_path(run_root))}): a new record's layout is read from the run's "
                 "own start download; run a session of the run on the camera, or take its old downloads in with "
                 "kit/tools/upload_check.py --adopt")
    return got


def like_setting(key: str, by_key: dict, e: dict, r: dict, like_table: dict, whole: set, start: Path,
                 run_name: str) -> dict:
    """A proved record the schema lacked, laid out like its sibling (`like_table`, the hand tables' NEW_LIKE: key ->
    (sibling, name)): size, count and memory-set presence from the run's start file (`start`, run_start), labels from
    the proofs (axis value alone, the whole label for a record `whole`, NEW_WHOLE_LABELS, lists); `run_name` the run
    its evidence names."""
    from camkit import camset
    like, name = like_table[key]
    rid = int(key.split("0x")[1], 16)
    cs = camset.read(start)
    rec = cs.get(0, rid)
    base = by_key[like]
    s = {f: base[f] for f in ("area", "source", "tab", "group", "order", "scalar", "modes") if f in base}
    vals = {} if "[field" in e["row"] else {v: clean(lab if key in whole else lab.split(":", 1)[-1].strip())
                                            for lab, v in r["proved"].items()}
    # the sibling's spelling of a label the proofs read the same ("ISO 160" for the box's "ISO160")
    sib = {v: lab for v, lab in base.get("values") or []}
    vals = {v: sib[v] if re.sub(r"\s+", "", str(sib.get(v, ""))).lower() == re.sub(r"\s+", "", lab).lower() else lab
            for v, lab in vals.items()}
    if vals and rec.value() not in vals:
        # the row's start value is not among the proofs: a gap there would tell the user's setting.
        # The sibling's labels fill it, as they agree with every proved one (S&Q's HD record, every
        # option proved, stores 25M as 29 where the movie one has 28, so no fill when not needed)
        for v, lab in base.get("values") or []:
            vals.setdefault(v, lab)
    # how it was found is evidence (camkit.definitions keeps note_evidence private): no note of its own
    s.update(key=key, id=rid, name=name, values=sorted([v, lab] for v, lab in vals.items()),
             note="", note_evidence=f"proved on the camera, laid out like {like} (runs/{run_name})",
             in_sets=cs.get(1, rid) is not None, size=rec.size, count=rec.count)
    return s


def by_lines_of(frame_proofs: dict) -> set:
    """The records a hand table lists values for but gives no proof (FRAME_PROOFS with "values" and without "proved" or
    "sampled": the Registered AF area records, whose holds are proof lines since 2026-11-09), proved by the report
    alone: what the table once listed is in the lines, and a value it listed that no line credits goes. An entry with a
    note only (AF Frame Move Amt's, 2026-11-09) is none of them: it sets the note, and the proof the definition holds
    is merged with the report's (kept_proof), as any setting's is."""
    return {k for k, fp in frame_proofs.items() if "values" in fp and not {"proved", "sampled"} & set(fp)}


def by_lines(tables, ev: dict) -> set:
    """by_lines_of for the plain pass, whose hand proofs are the hand evidence's, apart from the tables."""
    proofs = hand_proofs(ev)
    return {k for k, fp in tables.FRAME_PROOFS.items() if "values" in fp and k not in proofs}


def merged_values(values: list, key: str, tables) -> list:
    """A record's values as a hand table lists them whole (FRAME_PROOFS', NEW_RECORDS'), with the record's VALUE_FIXES
    names and its PP7_VALUES added, as the steps before put them: the whole list then says the same as those steps on
    every run, so a rerun changes nothing."""
    fixes = {v: lab for (k, v), lab in tables.VALUE_FIXES.items() if k == key}
    out = [[v, fixes.get(v, lab)] for v, lab in values]
    added = [[v, lab] for (k, v), lab in tables.PP7_VALUES.items() if k == key and v not in {x for x, _ in values}]
    return sorted(out + added) if added else out          # extra_values sorts the list it adds to


def evidence_words(ev: dict, tables: tuple, key) -> list:
    """A note's evidence for an entry: each "note+" the hand evidence gives it in `tables` (an entry FILTER_FLAGS and
    NEW_RECORDS share carries it in either), its parentheses aside, each part between "; " once (note_evidence keeps
    its parts so, and a rerun compares them so)."""
    out = []
    for t in tables:
        w = str(part(ev, t, key).get("note+") or "").strip()
        if w.startswith("(") and w.endswith(")"):
            w = w[1:-1].strip()
        for p in (x.strip() for x in w.split("; ")):
            if p and p not in out:
                out.append(p)
    return out


def hand_note(s: dict, note: str, words: list, changed: list) -> bool:
    """The setting's public note set to a hand table's `note`, word for word, and what the hand evidence says of it
    (`words`: a note's evidence, the owner's word) into note_evidence alone, which the definition keeps private: a
    note written whole takes the evidence of the one it replaces with it, as put_note does. A rerun on the same tables
    changes nothing (the owner's allowances a proof line adds after, writer/proofs.with_allowances, aside). Whether it
    changed."""
    have = [p for p in (s.get("note_evidence") or "").split("; ") if p]
    if s.get("note") == note and all(w in have for w in words) \
            and all(p in words or ALLOWANCE.fullmatch(p) for p in have):
        return False
    s["note"] = note
    if words:
        s["note_evidence"] = "; ".join(words)
    else:
        s.pop("note_evidence", None)
    changed.append((s["key"], s["name"], "note", None, note[:60]))
    return True


def new_records(doc: dict, by_key: dict, tables, ev: dict, cs, over: dict, changed: list, reported: set) -> None:
    """NEW_RECORDS (FILTER_FLAGS' entries among them): a record found by hand, its values named by the table ("hand
    table", counted unless a proof covers them: named_not_proved). One the definition holds keeps the table's name,
    values and note (a record FRAME_PROOFS fills keeps its values and note from there); one it lacks is added, laid out
    like the record `like` names (its area, tab, group, order and modes) and from the run's newest download (`cs`:
    size, count, memory-set presence), when the definition holds that record and the download holds this one; else it
    is said and left out. A note's evidence goes into note_evidence alone (hand_note). A record this step added
    before (its source "Derived", in the definition's evidence) that the table no longer holds and no row of the report
    names (`reported`: every key a row names, proved or not) is taken out, and said."""
    for s in list(doc["settings"]):
        if s.get("source") == "Derived" and s["key"] not in tables.NEW_RECORDS and s["key"] not in reported \
                and s["key"] not in tables.NEW_LIKE:
            print(f"  new record  {s['key']} {s['name'][:40]!r}: taken out, NEW_RECORDS no longer holds it and no row "
                  "of the report names it")
            doc["settings"].remove(s)
            by_key.pop(s["key"], None)
            changed.append((s["key"], s["name"], "dropped", s["name"], "(no longer in NEW_RECORDS)"))
    for k, info in tables.NEW_RECORDS.items():
        over[k].update({v: "hand table" for v, _ in info["values"]})
        words = evidence_words(ev, ("NEW_RECORDS", "FILTER_FLAGS"), k)
        if k in by_key:                              # added before: keep its words current
            want = {"name": info["name"], "values": merged_values(info["values"], k, tables)}
            fix = {f: _copy(want[f]) for f in ("name", "values") if fix_differs(by_key[k], {f: want[f]})
                   and not (k in tables.FRAME_PROOFS and f == "values")}
            if fix:
                changed.append((k, by_key[k]["name"], ",".join(fix), None, info["name"]))
                apply_fix(by_key[k], fix)
            if k not in tables.FRAME_PROOFS:
                hand_note(by_key[k], info["note"], words, changed)
            continue
        m = WHOLE.fullmatch(k)                       # refusals() stops a key that is no whole record first
        rec = cs.get(1 if m[1] == "set" else 0, int(m[2], 16)) if m else None
        if info["like"] not in by_key or rec is None:
            print(f"  new record  {k} {info['name'][:40]!r}: not added, "
                  + (f"the definition has no {info['like']} to lay it out like yet" if info["like"] not in by_key
                     else "the run's newest download holds no such record"))
            continue
        rid = int(m[2], 16)
        base = by_key[info["like"]]
        s = {f: base[f] for f in ("area", "tab", "group", "order", "scalar", "modes") if f in base}
        s.update(key=k, id=rid, name=info["name"], source="Derived", values=_copy(info["values"]), note=info["note"],
                 in_sets=cs.get(1, rid) is not None, size=rec.size, count=rec.count, scalar=rec.count == 1)
        if words and k not in tables.FRAME_PROOFS:
            s["note_evidence"] = "; ".join(words)
        doc["settings"].append(s)
        by_key[k] = s
        changed.append((k, s["name"], "new", None, info["values"]))


def value_fixes(by_key: dict, tables, over: dict, changed: list) -> None:
    """VALUE_FIXES: a value's name a proof cannot give, the table's ("hand table"; counted unless a proof covers it), on
    the setting where it lists the value; an entry for a setting the definition lacks, or a value it does not list,
    is said, not applied."""
    for (k, v), lab in tables.VALUE_FIXES.items():
        over[k][v] = "hand table"
        pairs = (by_key[k].get("values") or []) if k in by_key else []
        if not any(p[0] == v for p in pairs):
            print(f"  value fix  {k} {v}: not applied, " + ("the definition has no such setting yet" if k not in by_key
                                                            else "the setting lists no such value"))
        for pair in pairs:
            if pair[0] == v and pair[1] != lab:
                changed.append((k, by_key[k]["name"], v, pair[1], lab))
                pair[1] = lab


def record_fixes(by_key: dict, tables, ev: dict, changed: list) -> None:
    """RECORD_FIXES: a setting's name, tab, group, range or unit the camera proved wrong, put on it, and its note, word
    for word, its evidence into note_evidence alone (hand_note); one the definition does not hold yet is said."""
    for k, fix in tables.RECORD_FIXES.items():
        if k not in by_key:
            print(f"  record fix  {k} {fix['name'][:40]!r}: the definition has no such setting yet, not applied")
            continue
        rest = {f: x for f, x in fix.items() if f != "note"}
        if fix_differs(by_key[k], rest):
            changed.append((k, by_key[k]["name"], "name", by_key[k]["name"], fix["name"]))
            apply_fix(by_key[k], _copy(rest))
        if "note" in fix:
            hand_note(by_key[k], fix["note"], evidence_words(ev, ("RECORD_FIXES",), k), changed)


def unproved(doc: dict, by_key: dict, tables, ev: dict, changed: list, taken_out: set = None) -> None:
    """UNPROVED: why no proof can reach a setting, {kind, date (the hand evidence's, kept private), why}, on each
    setting it names that has no proof (its hand proof counting as one); a setting a proof reached, or the table no
    longer names, loses an old one, and an entry for a setting the definition lacks is said. A memory set's own block of
    the memories' live copy (camera.mirrors) says the same for the sets whose live field has a reason (unproved_sets).
    A day the hand evidence no longer gives is taken out on purpose: said, and added to `taken_out` (lost_evidence's
    words), so the write does not take it for evidence read away. Nothing when the table is empty and no setting holds
    either field."""
    taken_out = set() if taken_out is None else taken_out
    if not tables.UNPROVED and not any({"unproved_reason", "unproved_sets"} & set(s) for s in doc["settings"]):
        return
    for k in tables.UNPROVED:
        if k not in by_key:
            print(f"  unproved  {k}: the definition has no such setting yet, not applied")
    proofs = hand_proofs(ev)
    for k, r in by_key.items():
        why = None
        if not r.get("proved") and k in tables.UNPROVED and k not in proofs:
            kind, _date, text = tables.UNPROVED[k]
            date = part(ev, "UNPROVED", k).get("1")
            why = {"kind": kind, **({"date": date} if date else {}), "why": text}
        was = r.get("unproved_reason") or {}
        if why and "date" not in why and was.get("date"):
            print(f"  unproved  {k}: its day taken out, the hand evidence no longer gives one")
            taken_out.add(f"{k}: unproved_reason.date")
        if why and r.get("unproved_reason") != why:
            changed.append((k, r["name"], "unproved_reason", None, why["kind"]))
            r["unproved_reason"] = why
        elif not why and "unproved_reason" in r:
            del r["unproved_reason"]
    mirror = mirror_of(doc)
    for k, r in by_key.items():
        m = re.fullmatch(rf"set:0x{mirror['set_record']:04x}@(\d+)", k) if mirror.get("set_record") is not None else None
        if not m:
            continue
        reasons = {n: (by_key.get(mirror_key(mirror, n, int(m[1]))) or {}).get("unproved_reason")
                   for n in mirror.get("sections") or ()}
        sets = [n for n, w in reasons.items() if w]
        if sets:
            w = reasons[sets[0]]
            if not w.get("date") and (r.get("unproved_sets") or {}).get("date"):
                print(f"  unproved  {k}: the memory sets' day taken out, the hand evidence no longer gives one")
                taken_out.add(f"{k}: unproved_sets.date")
            r["unproved_sets"] = {"sets": sets, "kind": w["kind"], "why": w["why"],
                                  **({"date": w["date"]} if w.get("date") else {})}
        else:
            r.pop("unproved_sets", None)


def extra_values(by_key: dict, tables, over: dict, changed: list) -> None:
    """PP7_VALUES: values outside the camera's lists that its files hold, added to the setting's values ("hand table";
    counted unless a proof or a NOT_OFFERED held mark covers them); an entry for a setting the definition lacks is
    said, not applied."""
    for (k, v), lab in tables.PP7_VALUES.items():
        over[k][v] = "hand table"
        if k not in by_key:
            print(f"  extra value  {k} {v}: the definition has no such setting yet, not applied")
        elif v not in {x for x, _ in by_key[k].get("values") or []}:
            changed.append((k, by_key[k]["name"], v, None, lab))
            by_key[k]["values"] = sorted((by_key[k].get("values") or []) + [[v, lab]])


def frame_proofs(by_key: dict, tables, ev: dict, over: dict, changed: list, registered: dict, allowed: dict) -> None:
    """FRAME_PROOFS: what a record holds (its note, word for word; the note's evidence and the owner's word for a
    never-open row, from the hand evidence, into note_evidence alone, hand_note) and its values' names ("hand table",
    counted unless a proof covers them; a place on a grid losing its range); and, where the hand evidence gives one, its
    hand proof: the values or a sample, with the run, day and menu rows the evidence names (hand_proof_gaps refuses
    one without them), marked BY_HAND in the definition's evidence, the values a registration wrote there
    (`registered`, pass2_report.mirrored_values) credited under the table's labels and their allowance added to
    `allowed`. A record the definition does not hold is said; a hand proof an earlier run wrote that the hand evidence
    no longer gives is taken out, and said."""
    proofs = hand_proofs(ev)

    def recopied(k, s):
        """A copy of a family whose copies' modes are not known yet: writer/copies.py gives it its live setting's
        proof, by_hand and all, while the live one has one."""
        live = s.get("copy_of")
        return live in tables.COPY_MODES_UNKNOWN and k in (tables.COPIES.get(live) or ())

    def retract(k, s):
        print(f"  frame proof  {k}: its hand proof taken out, the hand evidence no longer gives one")
        s.pop("proved")
        changed.append((k, s["name"], "proved", None, "(no hand proof now)"))
    stale = [(k, s) for k, s in by_key.items() if (s.get("proved") or {}).get(BY_HAND) and k not in proofs]
    for k, s in stale:
        if not recopied(k, s):
            retract(k, s)
    for k, s in stale:                  # a copy goes with its live setting's proof, once that one has none left
        if recopied(k, s) and not (by_key.get(s["copy_of"]) or {}).get("proved"):
            retract(k, s)
    for k, fp in tables.FRAME_PROOFS.items():
        s = by_key.get(k)
        if s is None:
            print(f"  frame proof  {k}: the definition has no such setting (NEW_RECORDS adds a record found by hand), "
                  "not applied")
            continue
        hp = proofs.get(k) or {}
        words = evidence_words(ev, ("FRAME_PROOFS",), k)
        allowance = part(ev, "FRAME_PROOFS", k).get("allowance")
        hand_note(s, fp["note"], words + ([allowance] if allowance else []), changed)
        if "values" in fp:
            over[k].update({v: "hand table" for v, _ in fp["values"]})
            values = merged_values(fp["values"], k, tables)     # with the record's VALUE_FIXES and PP7_VALUES
            if fix_differs(s, {"values": values}):
                changed.append((k, s["name"], "values", None, str(values)[:40]))
                apply_fix(s, {"values": _copy(values)})
            if "range" in s:
                del s["range"]                     # a place on a grid, not a number
        if not hp:
            continue                               # names and note only: the report's proof stands (by_lines)
        menu = hp["menu"]
        proof = {"run": hp["run"], "date": hp["date"], "menu": sorted(menu) if isinstance(menu, list) else [menu]}
        if "proved" in hp and hp.get("linear"):
            # a scale whose proofs lie on a line, both ends among them (sampled_scale), is sampled: its values between
            # are inferred, and the proofs are not listed (the level put back is the camera's own)
            if sampled_scale(s, hp["proved"]):
                proof["sampled"] = {"proofs": len(hp["proved"]), "linear": True}
            else:
                print(f"  frame proofs  {k}: said to lie on a line, but its proofs do not (both ends, every proof on the "
                      "line); kept as proved values")
                proof["values"] = hp["proved"]
        else:
            proof.update({"values": hp["proved"]} if "proved" in hp else {"sampled": {"proofs": hp["sampled"], "linear": None}})
        got = registered.pop(k, None)
        if got and "values" in proof:
            # the values a registration wrote here, each under the table's own label; the latest run and day
            labels = dict((v, lab) for v, lab in fp.get("values") or s.get("values") or [])
            fits = {v for v, lab in got["values"].items() if labels.get(v) == lab}
            for v in sorted(set(got["values"]) - fits):
                print(f"  registered {k} {v}: the line calls it {got['values'][v]!r}, the table {labels.get(v)!r}; "
                      "not credited")
            proof["values"] = sorted(set(proof["values"]) | fits)
            if fits and (got["date"] or "", got["run"]) > (proof["date"], proof["run"]):
                proof.update(run=got["run"], date=got["date"])
            if got.get("allowance"):
                allowed[k].add(got["allowance"])
        proof[BY_HAND] = True
        if {f: x for f, x in (s.get("proved") or {}).items() if f != "names"} != proof:
            s["proved"] = proof
    for k in sorted(registered):        # registered values no hand table's proof took in: printed, not credited
        print(f"  registered {k}: {len(registered[k]['values'])} values registered ({registered[k]['run']}), but no "
              "hand table's proof of it takes them in; not credited")


def not_offered(doc: dict, tables, ev: dict, report: list, run_root: Path, derived: dict,
                taken_out: set = None) -> None:
    """NOT_OFFERED: each mark written while its evidence holds (writer/offered.py's not_offered_marks, the camera's
    table walk read where the runs hold it; what shows a mark, and a held value's downloads, from the hand evidence by
    the mark's place, into the mark's evidence, which the definition keeps private), and a held value named "derived"
    where the record its entry names (named_by) proved it under the mark's own label. A mark whose evidence the hand
    evidence no longer gives loses it on purpose: said, and added to `taken_out` (lost_evidence's words), so the write
    does not take it for evidence read away. Nothing when the table is empty and no setting holds a mark."""
    from runner import read_json

    from .offered import not_offered_marks
    taken_out = set() if taken_out is None else taken_out
    if not tables.NOT_OFFERED and not any("not_offered" in s for s in doc["settings"]):
        return
    had = {s["key"]: {json.dumps(m.get("value")) for m in s.get("not_offered") or [] if m.get("evidence")}
           for s in doc["settings"]}
    entries = [dict(entry, **{f: x for f, x in part(ev, "NOT_OFFERED", i).items() if f in ("evidence", "files")})
               for i, entry in enumerate(tables.NOT_OFFERED)]
    walk = run_root / "kit2_tables" / "tables.json"
    not_offered_marks(doc, entries, report, read_json(walk) if walk.exists() else {}, run_root)
    by_key = {s["key"]: s for s in doc["settings"]}
    for k, s in by_key.items():
        # each mark's part is its own (hand_evidence.plain_problems holds each part to its mark's "$key" and, where a
        # setting has several marks, "$values"), so a mark without evidence now is one whose part gives none
        gone = [m.get("value") for m in s.get("not_offered") or []
                if not m.get("evidence") and json.dumps(m.get("value")) in had.get(k, ())]
        for v in gone:
            print(f"  not offered  {k} {v}: the mark's evidence taken out, the hand evidence no longer gives it")
        if gone:
            taken_out.add(f"{k}: not_offered's evidence")
    for entry in tables.NOT_OFFERED:
        src, k = by_key.get(entry.get("named_by", "")), entry["key"]
        for m in (by_key.get(k) or {}).get("not_offered") or [] if src else []:
            if m["value"] in entry["values"] and m["value"] in ((src.get("proved") or {}).get("values") or ()) \
                    and dict((v, lab) for v, lab in src["values"]).get(m["value"]) == m["label"]:
                derived[k][m["value"]] = "derived"


def named_not_proved(doc: dict, over: dict) -> int:
    """A value a hand table names (over's "hand table") that no proof covers (the setting's proved values, the report's
    or a hand proof's) and no NOT_OFFERED mark holds (a factory value the camera writes): named, not proved, so its
    name's source is "counted", which the editor offers in Expert mode only. Returns how many."""
    n = 0
    for s in doc["settings"]:
        srcs = over.get(s["key"])
        if not srcs:
            continue
        seen = set((s.get("proved") or {}).get("values") or ())
        held = {m["value"] for m in s.get("not_offered") or [] if m.get("held")}
        for v, src in srcs.items():
            if src == "hand table" and v not in seen and v not in held:
                srcs[v] = "counted"
                n += 1
    return n


def like_fill_names(doc: dict, tables) -> int:
    """A record NEW_LIKE lays out like its sibling: each value it lists that its own proofs do not cover (the sibling's
    labels filled it, like_setting) is named as the sibling's value stands: "derived" where the sibling's value is
    established (among its lean proof's values, or any value of a scale sampled on its line), "counted" where it is not,
    so a value a hand table names on the sibling, counted there, never becomes checked through the fill. A name a hand
    table gave the value on the record itself ("hand table", "counted") stays. Run after with_names. Returns how many
    values it named counted."""
    from camkit.definitions import lean_proof

    from .labels import value_order
    by_key = {s["key"]: s for s in doc["settings"]}
    n = 0
    for k in like_order(tables):                # a sibling judged before the records laid out like it
        like = tables.NEW_LIKE[k][0]
        s, sib = by_key.get(k), by_key.get(like)
        p = (s or {}).get("proved")
        if not p or sib is None or (p.get("sampled") or {}).get("linear") is True:
            continue
        sp = sib.get("proved") or {}
        est = {v for v, _ in sib.get("values") or []} if (sp.get("sampled") or {}).get("linear") is True else \
            set(lean_proof(sp).get("values") or []) if sp else set()
        seen = set(p.get("values") or ())
        names = dict(p.get("names") or {})
        listed = [v for v, _ in s.get("values") or [] if not isinstance(v, (list, dict))]
        for v in listed:
            if v in seen or names.get(str(v)) not in (None, "derived"):
                continue
            names[str(v)] = "derived" if v in est else "counted"
            n += v not in est
        order = [str(v) for v in sorted(seen | set(listed), key=value_order)]
        names = {x: names[x] for x in order if x in names} | {x: src for x, src in names.items() if x not in order}
        p.pop("names", None)
        if names:
            p["names"] = names
    return n


def not_found(by_key: dict, tables) -> None:
    """The KEEP_LABELS and VIDEO_SYSTEM_VALUES entries for a setting the definition lacks, said: not applied."""
    for k in sorted(tables.KEEP_LABELS):
        if k not in by_key:
            print(f"  kept label  {k}: the definition has no such setting yet, not applied")
    for k in tables.VIDEO_SYSTEM_VALUES:
        if k not in by_key:
            print(f"  video system  {k}: the definition has no such setting yet, not applied")
